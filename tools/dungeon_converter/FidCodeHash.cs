// Cache key for the fidelity metric's Daggerfall side: a hash of the code that produces it. Walks the IL of
// LoadOrBuildDfSide and every method of this assembly it reaches (calls, lambdas, local functions), and hashes each
// body with its member references written as names, plus the current values of the static fields they read. So a
// change to the legal-position rule, the body test, the reach flood, the tier rule or a constant rebuilds the cache,
// and an unrelated converter change does not. Test tooling only (Fidelity.cs).
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

static partial class Program
{
    static readonly Dictionary<short, OpCode> FidOpCodes = typeof(OpCodes).GetFields(BindingFlags.Public | BindingFlags.Static)
        .Select(f => (OpCode)f.GetValue(null)).GroupBy(o => o.Value).ToDictionary(g => g.Key, g => g.First());

    // Compiler-generated names carry ordinals that shift when unrelated members are added.
    static string FidName(MemberInfo m)
    {
        string s = (m.DeclaringType?.FullName ?? "") + "::" + m.Name;
        if (m is MethodBase mb) s += "(" + string.Join(",", mb.GetParameters().Select(p => p.ParameterType.Name)) + ")";
        return s.Contains('<') ? Regex.Replace(s, @"\d+", "#") : s;
    }

    static string FidCodeHash()
    {
        var asm = typeof(Program).Assembly;
        var root = typeof(Program).GetMethod(nameof(LoadOrBuildDfSide), BindingFlags.NonPublic | BindingFlags.Static);
        // The face grid (cells, column tops) feeds the air flood, SkyOpen and the tiers but is built in RunFidelity.
        var grid = typeof(FidMeshGrid).GetConstructors(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)[0];
        var seen = new HashSet<MethodBase> { root, grid };
        var queue = new Queue<MethodBase>(seen);
        var bodies = new List<string>();
        while (queue.Count > 0)
        {
            var m = queue.Dequeue();
            var il = m.GetMethodBody()?.GetILAsByteArray();
            if (il == null) continue;
            var text = new StringBuilder(FidName(m)).Append('|');
            for (int p = 0; p < il.Length;)
            {
                short value = il[p] == 0xFE && p + 1 < il.Length ? (short)(0xFE00 | il[p + 1]) : il[p];
                if (!FidOpCodes.TryGetValue(value, out var op)) { text.Append('?').Append(il[p]); p++; continue; }
                p += op.Size;
                text.Append(op.Name).Append(' ');
                int size = op.OperandType switch
                {
                    OperandType.InlineNone => 0,
                    OperandType.ShortInlineBrTarget or OperandType.ShortInlineI or OperandType.ShortInlineVar => 1,
                    OperandType.InlineVar => 2,
                    OperandType.InlineI8 or OperandType.InlineR => 8,
                    OperandType.InlineSwitch => 4 + 4 * BitConverter.ToInt32(il, p),
                    _ => 4,
                };
                bool token = op.OperandType is OperandType.InlineMethod or OperandType.InlineField or OperandType.InlineType or OperandType.InlineTok or OperandType.InlineString;
                if (!token) { for (int k = 0; k < size; k++) text.Append(il[p + k].ToString("x2")); }
                else
                {
                    int t = BitConverter.ToInt32(il, p);
                    try
                    {
                        if (op.OperandType == OperandType.InlineString) text.Append('"').Append(m.Module.ResolveString(t)).Append('"');
                        else
                        {
                            var member = m.Module.ResolveMember(t, m.DeclaringType?.IsGenericType == true ? m.DeclaringType.GetGenericArguments() : null, m.IsGenericMethod ? m.GetGenericArguments() : null);
                            text.Append(member is Type ty ? ty.FullName : FidName(member));
                            if (member is MethodBase target && target.Module.Assembly == asm && seen.Add(target)) queue.Enqueue(target);
                            if (member is FieldInfo f && f.IsStatic && !f.IsLiteral && f.Module.Assembly == asm && (f.FieldType.IsPrimitive || f.FieldType == typeof(string)))
                                text.Append('=').Append(Convert.ToString(f.GetValue(null), System.Globalization.CultureInfo.InvariantCulture));
                            if (member is FieldInfo arr && arr.IsStatic && arr.IsInitOnly && arr.FieldType.IsArray && arr.GetValue(null) is Array values && values.Rank == 1 && arr.FieldType.GetElementType().IsPrimitive)
                                text.Append("=[").Append(string.Join(",", values.Cast<object>().Select(v => Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture)))).Append(']');
                        }
                    }
                    catch (Exception) { text.Append(t.ToString("x8")); }
                }
                text.Append(';');
                p += size;
            }
            bodies.Add(text.ToString());
        }
        bodies.Sort(StringComparer.Ordinal);
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n", bodies)));
        return bodies.Count + ":" + Convert.ToHexString(hash, 0, 12);
    }
}
