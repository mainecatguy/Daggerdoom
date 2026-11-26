<#
Starts overnight children in Windows jobs, dot-sourced by run.ps1 and queue.ps1 (lane hang fix, tools/lane_hang/README.md).
- A job holds every process a child starts, even after the child exits. When the child is done, Stop-LaneJob closes
  what it left behind, such as a test game, which otherwise kept running and held the lane open. Build helpers that
  are meant to stay open between builds are left running.
- The child inherits only its three redirect files. Start-Process passes on every inheritable handle, including the
  caller's own output pipe, so a kept helper below the child could hold that pipe open for as long as it lives.
#>

# Left running when a job ends. Names are matched without case. dotnet.exe is kept only when it hosts a build server.
$LaneJobKeep = @(
    'MSBuild.exe', 'mspdbsrv.exe', 'VBCSCompiler.exe', 'vctip.exe',   # MSBuild reuse nodes, PDB server, C# compiler server
    'Unity.Licensing.Client.exe', 'Unity Hub.exe',                    # Unity's license client and Hub
    'conhost.exe'                                                     # closes by itself with its console program
)
$LaneJobKeepDotnet = 'MSBuild\.dll|VBCSCompiler\.dll|rzc\.dll'

if (-not ('LaneJob' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
public class LaneChild { public Process Process; public IntPtr Job; }
public static class LaneJob {
    [StructLayout(LayoutKind.Sequential)]
    struct Limits {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit; public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize; public uint ActiveProcessLimit;
        public UIntPtr Affinity; public uint PriorityClass, SchedulingClass;
        public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct Security { public int Length; public IntPtr Descriptor; public bool Inherit; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct StartupInfoEx {
        public int cb; public string Reserved, Desktop, Title;
        public int X, Y, XSize, YSize, XCountChars, YCountChars, FillAttribute, Flags;
        public short ShowWindow, Reserved2; public IntPtr Reserved3, StdInput, StdOutput, StdError, AttributeList;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct ProcessInfo { public IntPtr Process, Thread; public int ProcessId, ThreadId; }

    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr CreateJobObject(IntPtr security, string name);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref Limits info, int size);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool QueryInformationJobObject(IntPtr job, int infoClass, IntPtr info, int size, IntPtr returned);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool IsProcessInJob(IntPtr process, IntPtr job, out bool result);
    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool TerminateProcess(IntPtr process, uint exitCode);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateFile(string name, uint access, uint share, ref Security security, uint disposition, uint flags, IntPtr template);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool InitializeProcThreadAttributeList(IntPtr list, int count, int flags, ref IntPtr size);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool UpdateProcThreadAttribute(IntPtr list, int flags, IntPtr attribute, IntPtr value, IntPtr size, IntPtr previous, IntPtr returnSize);
    [DllImport("kernel32.dll")] static extern void DeleteProcThreadAttributeList(IntPtr list);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool CreateProcess(string app, System.Text.StringBuilder commandLine, IntPtr processSecurity, IntPtr threadSecurity,
        bool inherit, uint flags, IntPtr environment, string cwd, ref StartupInfoEx startup, out ProcessInfo info);
    [DllImport("kernel32.dll")] static extern uint ResumeThread(IntPtr thread);

    static IntPtr Open(string path, bool write) {
        Security s = new Security(); s.Length = Marshal.SizeOf(typeof(Security)); s.Inherit = true;
        // Read: open existing, share all. Write: create or truncate, share read and write.
        IntPtr h = CreateFile(path, write ? 0x40000000u : 0x80000000u, 7, ref s, write ? 2u : 3u, 0x80, IntPtr.Zero);
        if (h == new IntPtr(-1)) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error(), path);
        return h;
    }

    // Starts exe (a full path) with stdin, stdout and stderr from these files and no other inherited handle. It joins
    // a new job before it runs. Job is IntPtr.Zero if no job could be made; the child then runs without one.
    public static LaneChild Run(string exe, string args, string cwd, string inPath, string outPath, string errPath) {
        IntPtr[] handles = new IntPtr[3];
        IntPtr list = IntPtr.Zero, handleList = IntPtr.Zero;
        LaneChild child = new LaneChild();
        try {
            handles[0] = Open(inPath, false); handles[1] = Open(outPath, true); handles[2] = Open(errPath, true);
            IntPtr size = IntPtr.Zero;
            InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref size);
            list = Marshal.AllocHGlobal(size);
            if (!InitializeProcThreadAttributeList(list, 1, 0, ref size)) throw new System.ComponentModel.Win32Exception();
            handleList = Marshal.AllocHGlobal(IntPtr.Size * 3);
            Marshal.Copy(handles, 0, handleList, 3);
            if (!UpdateProcThreadAttribute(list, 0, (IntPtr)0x20002, handleList, (IntPtr)(IntPtr.Size * 3), IntPtr.Zero, IntPtr.Zero))
                throw new System.ComponentModel.Win32Exception();
            StartupInfoEx si = new StartupInfoEx();
            si.cb = Marshal.SizeOf(typeof(StartupInfoEx)); si.Flags = 0x100;   // use std handles
            si.StdInput = handles[0]; si.StdOutput = handles[1]; si.StdError = handles[2]; si.AttributeList = list;
            ProcessInfo pi;
            System.Text.StringBuilder line = new System.Text.StringBuilder("\"" + exe + "\" " + args);
            // Extended startup info, suspended, so it can join the job before it starts anything.
            if (!CreateProcess(exe, line, IntPtr.Zero, IntPtr.Zero, true, 0x80000 | 0x4, IntPtr.Zero, cwd, ref si, out pi))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error(), exe);
            try {
                child.Job = CreateJobObject(IntPtr.Zero, null);
                Limits limits = new Limits(); limits.LimitFlags = 0x800;   // breakaway allowed for programs that ask
                if (child.Job != IntPtr.Zero && (!SetInformationJobObject(child.Job, 9, ref limits, Marshal.SizeOf(typeof(Limits)))
                        || !AssignProcessToJobObject(child.Job, pi.Process))) {
                    CloseHandle(child.Job); child.Job = IntPtr.Zero;
                }
                child.Process = Process.GetProcessById(pi.ProcessId);
                IntPtr keep = child.Process.Handle;   // opened while it cannot exit, so ExitCode stays readable
            } finally {
                ResumeThread(pi.Thread); CloseHandle(pi.Thread); CloseHandle(pi.Process);
            }
            return child;
        } finally {
            foreach (IntPtr h in handles) if (h != IntPtr.Zero && h != new IntPtr(-1)) CloseHandle(h);
            if (list != IntPtr.Zero) { DeleteProcThreadAttributeList(list); Marshal.FreeHGlobal(list); }
            if (handleList != IntPtr.Zero) Marshal.FreeHGlobal(handleList);
        }
    }

    // Process ids in the job, including nested jobs.
    public static int[] Pids(IntPtr job) {
        int max = 4096, size = 8 + max * IntPtr.Size;
        IntPtr buffer = Marshal.AllocHGlobal(size);
        try {
            if (!QueryInformationJobObject(job, 3, buffer, size, IntPtr.Zero)) return new int[0];
            int count = Marshal.ReadInt32(buffer, 4);
            int[] pids = new int[count];
            for (int i = 0; i < count; i++) pids[i] = (int)Marshal.ReadIntPtr(buffer, 8 + i * IntPtr.Size).ToInt64();
            return pids;
        } finally { Marshal.FreeHGlobal(buffer); }
    }

    // Ends the process only if it is still in the job, so a reused process id is never hit.
    public static bool Kill(IntPtr job, int pid) {
        IntPtr process = OpenProcess(0x1001, false, pid);   // terminate, query limited information
        if (process == IntPtr.Zero) return false;
        try {
            bool inJob;
            return IsProcessInJob(process, job, out inJob) && inJob && TerminateProcess(process, 1);
        } finally { CloseHandle(process); }
    }
}
'@
}

# Starts a child in a new job with only its redirect files inherited (stdin defaults to NUL). Returns a LaneChild:
# .Process, and .Job for Stop-LaneJob (IntPtr.Zero if no job could be made).
function Start-LaneChild([string]$Exe, [string]$ArgLine, [string]$WorkingDirectory, [string]$In = 'NUL',
                         [string]$Out, [string]$Err) {
    $path = (Get-Command $Exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $full = { param($p) if ($p -eq 'NUL') { $p } else { $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($p) } }
    if (-not $WorkingDirectory) { $WorkingDirectory = (Get-Location -PSProvider FileSystem).ProviderPath }
    if ($path -match '\.(cmd|bat)$') {   # a batch shim, such as an npm-installed claude
        $ArgLine = "/d /s /c `"`"$path`" $ArgLine`""; $path = $env:ComSpec
    }
    $child = [LaneJob]::Run($path, $ArgLine, (& $full $WorkingDirectory), (& $full $In), (& $full $Out), (& $full $Err))
    if ($child.Job -eq [IntPtr]::Zero) { Write-Host "Could not put $Exe in a job. Its leftovers may outlive it." }
    $child
}

# Ends every process left in the job except kept build helpers, then closes the job. Returns the names it ended.
function Stop-LaneJob([IntPtr]$Job) {
    if ($Job -eq [IntPtr]::Zero) { return }
    $ended = @()
    try {
        # A few passes, in case a process starts another while the first is ending.
        for ($pass = 0; $pass -lt 5; $pass++) {
            $pids = [LaneJob]::Pids($Job)
            if (-not $pids.Count) { break }
            $info = @{}
            Get-CimInstance Win32_Process -Filter (($pids | ForEach-Object { "ProcessId=$_" }) -join ' OR ') |
                ForEach-Object { $info[[int]$_.ProcessId] = $_ }
            $targets = @($pids | Where-Object {
                    $p = $info[[int]$_]
                    $p -and $LaneJobKeep -notcontains $p.Name -and
                    -not ($p.Name -eq 'dotnet.exe' -and $p.CommandLine -match $LaneJobKeepDotnet)
                })
            if (-not $targets.Count) { break }
            foreach ($id in $targets) { if ([LaneJob]::Kill($Job, $id)) { $ended += $info[[int]$id].Name } }
            Start-Sleep -Milliseconds 200
        }
    }
    finally { $null = [LaneJob]::CloseHandle($Job) }
    $ended
}
