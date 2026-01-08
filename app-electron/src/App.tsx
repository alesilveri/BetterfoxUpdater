import './theme.css';

import { useCallback, useEffect, useMemo, useState } from 'react';

type Stat = { label: string; value: string; tone?: 'ok' | 'warn' | 'err' };
type StatusTone = 'ok' | 'warn' | 'err' | 'busy';
type StatusState = { label: string; detail: string; tone: StatusTone };

const STAT_TEMPLATE: Stat[] = [
  { label: 'Locale', value: 'n/d' },
  { label: 'Remoto', value: 'n/d' },
  { label: 'GitHub', value: 'n/d' },
  { label: 'Firefox', value: 'n/d' },
];

const DEFAULT_STATUS: StatusState = {
  label: 'Pronto',
  detail: 'Seleziona un profilo per iniziare.',
  tone: 'ok',
};

const formatErr = (err: unknown) => (err instanceof Error ? err.message : 'Errore sconosciuto');

function Pill({ stat }: { stat: Stat }) {
  return (
    <div className="pill">
      <span className="pill-label">{stat.label}</span>
      <span className={`pill-value ${stat.tone ?? ''}`}>{stat.value}</span>
    </div>
  );
}

function App() {
  const [profilePath, setProfilePath] = useState('');
  const [profiles, setProfiles] = useState<{ name: string; path: string }[]>([]);
  const [backupPath, setBackupPath] = useState('');
  const [retention, setRetention] = useState(45);
  const [log, setLog] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<StatusState>(DEFAULT_STATUS);
  const [autoBackup, setAutoBackup] = useState(true);
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system');
  const [stats, setStats] = useState<Stat[]>(() => [...STAT_TEMPLATE]);
  const [appVersion, setAppVersion] = useState('');
  const [lastUpdateOk, setLastUpdateOk] = useState(false);
  const [needsRestart, setNeedsRestart] = useState(false);

  const heroMeta = useMemo(
    () => ({
      title: 'Betterfox Updater',
      subtitle: 'Aggiorna user.js con backup sicuri e percorso guidato.',
    }),
    []
  );

  const setStatusState = useCallback((label: string, detail: string, tone: StatusTone) => {
    setStatus({ label, detail, tone });
  }, []);

  const appendLog = useCallback((items: string | string[]) => {
    const entries = Array.isArray(items) ? items : [items];
    setLog((prev) => [...entries, ...prev].slice(0, 200));
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem('bf-theme');
    if (saved === 'light' || saved === 'dark' || saved === 'system') setTheme(saved);
  }, []);

  useEffect(() => {
    const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    const effective = theme === 'dark' || (theme === 'system' && prefersDark) ? 'dark' : 'light';
    document.documentElement.dataset.theme = effective;
    localStorage.setItem('bf-theme', theme);
  }, [theme]);

  useEffect(() => {
    window.bf.getVersion().then(setAppVersion).catch(() => {});
  }, []);

  useEffect(() => {
    setLastUpdateOk(false);
    setNeedsRestart(false);
  }, [profilePath]);

  useEffect(() => {
    if (theme !== 'system') return;
    const mql = window.matchMedia?.('(prefers-color-scheme: dark)');
    const onChange = () => {
      const effective = mql?.matches ? 'dark' : 'light';
      document.documentElement.dataset.theme = effective;
    };
    mql?.addEventListener('change', onChange);
    return () => mql?.removeEventListener('change', onChange);
  }, [theme]);

  const loadProfiles = useCallback(async () => {
    try {
      const found = await window.bf.listProfiles();
      setProfiles(found);
      if (!profilePath && found.length > 0) setProfilePath(found[0].path);
    } catch (err) {
      appendLog(`Errore: impossibile leggere i profili (${formatErr(err)}).`);
    }
  }, [profilePath, appendLog]);

  const refreshVersions = useCallback(async () => {
    setStatusState('In corso', 'Controllo versioni in corso.', 'busy');
    setProgress(22);
    try {
      const res = await window.bf.checkVersions(profilePath || undefined);
      setStats([
        { label: 'Locale', value: res.local },
        { label: 'Remoto', value: res.remote, tone: res.remote !== res.local ? 'ok' : undefined },
        { label: 'GitHub', value: res.github, tone: res.github !== 'n/d' ? 'ok' : undefined },
        { label: 'Firefox', value: res.firefox },
      ]);
      setStatusState('Pronto', 'Versioni aggiornate.', 'ok');
    } catch (err) {
      appendLog(`Errore: controllo versioni non riuscito (${formatErr(err)}).`);
      setStatusState('Errore', 'Controllo versioni non riuscito.', 'err');
    } finally {
      setTimeout(() => setProgress(0), 700);
    }
  }, [profilePath, setStatusState, appendLog]);

  const chooseProfileDir = useCallback(async () => {
    const dir = await window.bf.chooseDir();
    if (dir) setProfilePath(dir);
  }, []);

  const chooseBackupDir = useCallback(async () => {
    const dir = await window.bf.chooseDir();
    if (dir) setBackupPath(dir);
  }, []);

  const runBackup = useCallback(async () => {
    if (!profilePath || !backupPath) {
      appendLog('Errore: seleziona profilo e cartella backup prima di continuare.');
      setStatusState('Errore', 'Profilo o backup mancante.', 'err');
      return;
    }
    setStatusState('In corso', 'Backup in esecuzione.', 'busy');
    setProgress(40);
    const res = await window.bf.backupProfile({ profilePath, destPath: backupPath, retentionDays: retention });
    appendLog(res.log);
    setStatusState(res.ok ? 'Pronto' : 'Errore', res.ok ? 'Backup completato.' : 'Backup non riuscito.', res.ok ? 'ok' : 'err');
    setTimeout(() => setProgress(0), 700);
  }, [appendLog, backupPath, profilePath, retention, setStatusState]);

  const runUpdate = useCallback(async () => {
    if (!profilePath) {
      appendLog('Errore: seleziona un profilo Firefox prima di aggiornare.');
      setStatusState('Errore', 'Profilo non impostato.', 'err');
      setLastUpdateOk(false);
      return;
    }
    setStatusState('In corso', 'Aggiornamento in corso.', 'busy');
    setProgress(28);
    if (autoBackup && backupPath) {
      const bk = await window.bf.backupProfile({ profilePath, destPath: backupPath, retentionDays: retention });
      appendLog(bk.log);
      if (!bk.ok) {
        appendLog('Avviso: backup non riuscito, continuo con update.');
        setStatusState('Attenzione', 'Backup non riuscito, continuo con update.', 'warn');
      }
    } else if (autoBackup) {
      appendLog('Avviso: backup saltato, cartella non configurata.');
      setStatusState('Attenzione', 'Backup non configurato, continuo con update.', 'warn');
    }
    const res = await window.bf.updateBetterfox({ profilePath });
    appendLog(res.log);
    if (res.version) {
      setStats((prev) => prev.map((s) => (s.label === 'Locale' ? { ...s, value: res.version! } : s)));
    }
    setLastUpdateOk(res.ok);
    setNeedsRestart(res.ok);
    setStatusState(
      res.ok ? 'Pronto' : 'Errore',
      res.ok ? 'Aggiornamento completato. Riavvia Firefox.' : 'Aggiornamento non riuscito.',
      res.ok ? 'ok' : 'err'
    );
    setTimeout(() => setProgress(0), 700);
  }, [appendLog, autoBackup, backupPath, profilePath, retention, setStatusState]);

  const openPathSafe = async (path?: string) => {
    if (!path) {
      appendLog('Errore: percorso non disponibile.');
      return;
    }
    await window.bf.openPath(path);
  };

  const markRestarted = useCallback(() => {
    setNeedsRestart(false);
    appendLog('OK: Firefox riavviato.');
    setStatusState('Pronto', 'Firefox riavviato.', 'ok');
  }, [appendLog, setStatusState]);

  const nextStepId = useMemo(() => {
    if (!profilePath) return 'profile';
    if (autoBackup && !backupPath) return 'backup';
    if (!lastUpdateOk) return 'update';
    if (needsRestart) return 'restart';
    return 'done';
  }, [profilePath, backupPath, autoBackup, lastUpdateOk, needsRestart]);

  const nextStepMeta = useMemo(() => {
    switch (nextStepId) {
      case 'profile':
        return { label: 'Seleziona un profilo Firefox per continuare.', actionLabel: 'Scegli profilo' };
      case 'backup':
        return { label: 'Imposta una cartella backup consigliata.', actionLabel: 'Scegli backup' };
      case 'update':
        return { label: 'Esegui update per allineare user.js.', actionLabel: 'Esegui update' };
      case 'restart':
        return { label: 'Riavvia Firefox per applicare le modifiche.', actionLabel: 'Ho riavviato' };
      default:
        return { label: 'Tutto pronto. Nessun passo in sospeso.' };
    }
  }, [nextStepId]);

  const activeStepIndex = useMemo(() => {
    switch (nextStepId) {
      case 'profile':
        return 0;
      case 'backup':
        return 1;
      case 'update':
        return 2;
      case 'restart':
        return 3;
      default:
        return -1;
    }
  }, [nextStepId]);

  const runNextStep = useCallback(async () => {
    switch (nextStepId) {
      case 'profile':
        await chooseProfileDir();
        return;
      case 'backup':
        await chooseBackupDir();
        return;
      case 'update':
        await runUpdate();
        return;
      case 'restart':
        markRestarted();
        return;
      default:
        return;
    }
  }, [nextStepId, chooseProfileDir, chooseBackupDir, runUpdate, markRestarted]);

  const steps = useMemo(() => {
    const backupReady = !!backupPath || !autoBackup;
    return [
      { label: 'Seleziona profilo Firefox', done: !!profilePath, active: activeStepIndex === 0 },
      { label: autoBackup ? 'Imposta cartella backup' : 'Backup opzionale disattivato', done: backupReady, active: activeStepIndex === 1 },
      { label: 'Esegui update', done: lastUpdateOk, active: activeStepIndex === 2 },
      { label: 'Riavvia Firefox', done: lastUpdateOk && !needsRestart, active: activeStepIndex === 3 },
    ];
  }, [profilePath, backupPath, autoBackup, lastUpdateOk, needsRestart, activeStepIndex]);

  useEffect(() => {
    loadProfiles();
    refreshVersions();
  }, [loadProfiles, refreshVersions]);

  const canUpdate = !!profilePath;
  const canBackup = !!profilePath && !!backupPath;

  const quickActions = [
    { label: 'Aggiorna Betterfox', tone: 'primary', onClick: runUpdate, disabled: !canUpdate },
    { label: 'Backup profilo', tone: 'ghost', onClick: runBackup, disabled: !canBackup },
    { label: 'Controlla versioni', tone: 'ghost', onClick: refreshVersions },
  ];

  const links = [
    { label: 'Apri user.js', onClick: () => openPathSafe(profilePath ? `${profilePath}\\user.js` : '') },
    { label: 'Betterfox GitHub', onClick: () => window.bf.openUrl('https://github.com/yokoffing/Betterfox') },
    { label: 'Release Betterfox', onClick: () => window.bf.openUrl('https://github.com/yokoffing/Betterfox/releases') },
    { label: 'Changelog Betterfox', onClick: () => window.bf.openUrl('https://github.com/yokoffing/Betterfox/blob/main/CHANGELOG.md') },
    { label: 'Cartella backup', onClick: () => openPathSafe(backupPath) },
    { label: 'Apri profilo', onClick: () => openPathSafe(profilePath) },
  ];

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-text">
          <div className="eyebrow">Progetto personale</div>
          <div className="title-row">
            <h1>{heroMeta.title}</h1>
            {appVersion ? <span className="version-pill">v{appVersion}</span> : null}
          </div>
          <p className="muted">{heroMeta.subtitle}</p>
          <div className="hero-tags">
            <span className="chip">Percorso guidato</span>
            <span className="chip">Backup sicuro</span>
            <span className="chip">Versioni rapide</span>
          </div>
          <div className="hero-actions">
            <button className="btn primary" onClick={runUpdate} disabled={!canUpdate}>Aggiorna ora</button>
            <button className="btn ghost" onClick={runBackup} disabled={!canBackup}>Solo backup</button>
            <button className="btn ghost" onClick={() => window.bf.openUrl('https://github.com/yokoffing/Betterfox/releases')}>Release Betterfox</button>
          </div>
        </div>
        <div className="hero-panel">
          <div className="status-stack">
            <div className={`status-chip large ${status.tone}`}>{status.label}</div>
            <div className="status-detail muted small">{status.detail}</div>
            <div className="progress subtle mini">
              <div className="bar" style={{ width: `${Math.min(progress, 100)}%` }}></div>
            </div>
            <div className="micro muted">
              Profilo: {profilePath ? 'selezionato' : 'non impostato'} | Backup: {backupPath ? 'configurato' : 'mancante'} | Riavvio: {needsRestart ? 'richiesto' : 'ok'}
            </div>
            {needsRestart ? (
              <button className="btn ghost small" onClick={markRestarted}>Ho riavviato Firefox</button>
            ) : null}
          </div>
          <div className="theme-toggle">
            <span>Tema</span>
            <div className="toggle-buttons">
              <button className={theme === 'system' ? 'active' : ''} onClick={() => setTheme('system')}>Sistema</button>
              <button className={theme === 'light' ? 'active' : ''} onClick={() => setTheme('light')}>Light</button>
              <button className={theme === 'dark' ? 'active' : ''} onClick={() => setTheme('dark')}>Dark</button>
            </div>
          </div>
          <div className="hero-links">
            <button className="btn ghost small" onClick={() => openPathSafe(profilePath)}>Apri profilo</button>
            <button className="btn ghost small" onClick={() => openPathSafe(backupPath)}>Apri backup</button>
          </div>
        </div>
      </header>

      <section className="card stats">
        <div className="card-title">Versioni in vista</div>
        <div className="pill-row">
          {stats.map((s) => (
            <Pill key={s.label} stat={s} />
          ))}
        </div>
      </section>

      <main className="grid layout">
        <section className="card form">
          <div className="card-title">Percorsi e update</div>
          <p className="muted small">Imposta profilo, cartella backup e lancia update con un click.</p>
          <div className="step-list">
            {steps.map((step, idx) => (
              <div key={step.label} className={`step ${step.done ? 'done' : ''} ${step.active ? 'active' : ''}`}>
                <span className="step-index">{idx + 1}</span>
                <span>{step.label}</span>
              </div>
            ))}
          </div>
          <div className="next-step">
            <div className="muted small">Prossimo step</div>
            <div className="next-step-row">
              <span>{nextStepMeta.label}</span>
              {nextStepMeta.actionLabel ? (
                <button className="btn ghost small" onClick={runNextStep}>
                  {nextStepMeta.actionLabel}
                </button>
              ) : null}
            </div>
          </div>
          <div className="actions-row primary">
            {quickActions.map((a) => (
              <button
                key={a.label}
                className={`btn ${a.tone === 'primary' ? 'primary' : 'ghost'}`}
                onClick={a.onClick}
                disabled={a.disabled}
              >
                {a.label}
              </button>
            ))}
          </div>
          <div className="form-row">
            <label>Profilo Firefox</label>
            <div className="field">
              <input
                placeholder="C:\\Utenti\\...\\profile"
                value={profilePath}
                onChange={(e) => setProfilePath(e.target.value)}
              />
              <button className="btn ghost" onClick={chooseProfileDir}>Sfoglia</button>
            </div>
          </div>
          <div className="form-row">
            <label>Profili rilevati</label>
            <div className="field">
              <select value={profilePath} onChange={(e) => setProfilePath(e.target.value)}>
                {profiles.length === 0 ? <option value="">Nessun profilo</option> : null}
                {profiles.map((p) => (
                  <option key={p.path} value={p.path}>{p.name}</option>
                ))}
              </select>
              <button className="btn ghost" onClick={loadProfiles}>Rileva</button>
            </div>
          </div>
          <div className="form-row">
            <label>Cartella backup</label>
            <div className="field">
              <input
                placeholder="C:\\BetterfoxUp\\backups"
                value={backupPath}
                onChange={(e) => setBackupPath(e.target.value)}
              />
              <button className="btn ghost" onClick={chooseBackupDir}>Scegli</button>
            </div>
          </div>
          <div className="form-row two compact-pair">
            <div>
              <label>Retention (giorni)</label>
              <input type="number" min={7} max={120} value={retention} onChange={(e) => setRetention(Number(e.target.value))} />
            </div>
            <div className="toggle-row compact">
              <label className="inline">
                <input type="checkbox" checked={autoBackup} onChange={(e) => setAutoBackup(e.target.checked)} /> Backup prima di aggiornare
              </label>
            </div>
          </div>
        </section>

        <section className="card log">
          <div className="card-title">Log e link rapidi</div>
          <div className="log-box">
            {log.length === 0 ? <div className="muted">Nessun log</div> : log.map((item, idx) => <div key={idx}>{item}</div>)}
          </div>
          <div className="actions-row utility">
            <button className="btn ghost small" onClick={() => setLog([])}>Pulisci log</button>
            <button className="btn ghost small" onClick={() => refreshVersions()}>Ricarica versioni</button>
          </div>
          <div className="links-grid compact">
            {links.map((l) => (
              <button key={l.label} className="btn ghost small" onClick={l.onClick}>{l.label}</button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
