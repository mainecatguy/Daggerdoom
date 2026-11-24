// Test hook: with +set dd_encounter_pooldump 1, prints the whole encounter pool once, on the first map loaded,
// as lines starting with "ENCPOOL", ending with "ENCPOOL done". Use with -stdout or +logfile. tools/encounter_pool runs it.
class DoomerfallEncounterPoolDump : StaticEventHandler
{
	bool dumped;

	override void WorldLoaded(WorldEvent e)
	{
		if (dumped) return;
		let flag = CVar.FindCVar("dd_encounter_pooldump");
		if (!flag || !flag.GetBool()) return;
		dumped = true;
		let pool = DoomerfallEncounterPool.Get();
		if (!pool) { Console.Printf("ENCPOOL error no-pool"); Console.Printf("ENCPOOL done"); return; }
		let d = pool.data;
		Console.Printf("ENCPOOL begin classes=%d", AllActorClasses.Size());
		for (int i = 0; i < d.errors.Size(); i++) Console.Printf("ENCPOOL data-error %s", d.errors[i]);

		int safe = 0, capped = 0;
		Array<int> perTier;
		for (int t = 0; t <= 8; t++) perTier.Push(0);
		for (int i = 0; i < pool.monsters.Size(); i++)
		{
			let m = pool.monsters[i];
			if (m.civilWarSafe) safe++;
			if (m.capped) capped++;
			perTier[clamp(m.tier, 0, 8)]++;
			Console.Printf("ENCPOOL monster %s kind=%s tier=%d group=%s points=%.2f health=%d radius=%.0f height=%.0f traits=%s capped=%d civilwar=%s",
				m.cls.GetClassName(), d.kindName[m.kind], m.tier, m.group, m.points, m.health, m.radius, m.height,
				DoomerfallMonster.TraitNames(m.traits), m.capped, m.civilWarSafe ? "safe" : "unsafe:" .. m.unsafeWhy);
		}
		for (int i = 0; i < pool.excludedName.Size(); i++) Console.Printf("ENCPOOL skipped %s %s", pool.excludedName[i], pool.excludedWhy[i]);
		for (int k = 0; k < d.kindName.Size(); k++) Console.Printf("ENCPOOL kind %s count=%d", d.kindName[k], pool.CountKind(k));
		for (int t = 1; t <= 8; t++) Console.Printf("ENCPOOL tier %d count=%d", t, perTier[t]);
		Console.Printf("ENCPOOL curve L0=%.2f L1=%.2f L5=%.2f L10=%.2f L15=%.2f L20=%.2f L25=%.2f L30=%.2f",
			d.AveragePoints(0), d.AveragePoints(1), d.AveragePoints(5), d.AveragePoints(10), d.AveragePoints(15),
			d.AveragePoints(20), d.AveragePoints(25), d.AveragePoints(30));
		Console.Printf("ENCPOOL titan L19=%.2f L20=%.2f L25=%.2f L30=%.2f", d.TitanChanceAt(19), d.TitanChanceAt(20), d.TitanChanceAt(25), d.TitanChanceAt(30));
		Console.Printf("ENCPOOL data themes=%d groups=%d tierrules=%d ownrules=%d boss_max=%.0f capped_share=%.2f crypt_kinds=%s",
			d.ThemeCount(), d.groupName.Size(), d.tierPat.Size(), d.ownPat.Size(), d.Value("boss_max"), d.Value("capped_share"),
			d.ThemeGet("Crypt", "kinds"));
		Console.Printf("ENCPOOL summary monsters=%d civilwar_safe=%d capped=%d skipped=%d data_errors=%d",
			pool.monsters.Size(), safe, capped, pool.excludedName.Size(), d.errors.Size());
		Console.Printf("ENCPOOL done");
	}
}
