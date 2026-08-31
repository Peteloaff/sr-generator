"use client";

import { useCallback, useEffect, useState } from "react";
import { api, getBandId, type BandAdapter, type BandReference } from "@/lib/api";

export default function ReferencesPage() {
  const [bandId, setBandId] = useState<string | null>(null);
  const [refs, setRefs] = useState<BandReference[]>([]);
  const [dna, setDna] = useState<Record<string, unknown> | null>(null);
  const [manifest, setManifest] = useState<{ status: number; body: unknown } | null>(null);
  const [adapters, setAdapters] = useState<BandAdapter[]>([]);
  const [folder, setFolder] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (bid: string) => {
    const [r, d, m, a] = await Promise.all([
      api.listReferences(bid),
      api.bandDna(bid),
      api.trainingManifest(bid),
      api.listAdapters(bid),
    ]);
    setRefs(r);
    setDna(d);
    setManifest(m);
    setAdapters(a);
  }, []);

  useEffect(() => {
    (async () => {
      const bid = getBandId() ?? (await api.listBands())[0]?.id ?? null;
      setBandId(bid);
      if (bid) load(bid);
    })();
  }, [load]);

  const run = async (label: string, fn: () => Promise<{ id?: string }>) => {
    if (!bandId) return;
    setBusy(label);
    setErr(null);
    try {
      const job = await fn();
      if (job.id) await api.waitJob(job.id);
      await load(bandId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  const toggleApprove = async (r: BandReference) => {
    try {
      await api.updateReference(r.id, { approved_for_training: !r.approved_for_training });
      if (bandId) load(bandId);
    } catch (e) {
      setErr(String(e));
    }
  };

  const bpm = dna?.bpm as { mean?: number; min?: number; max?: number } | null;
  const keyDist = (dna?.key_distribution ?? {}) as Record<string, number>;

  return (
    <div>
      <h1>Band DNA</h1>
      <p className="muted">
        Point at a folder of your catalogue — every audio file becomes a reference
        and is analysed (BPM, key, tuning, structure). Approve the good ones, then
        generate a reproducible training manifest.
      </p>
      {err && <p className="danger">{err}</p>}

      <div className="row">
        <input
          placeholder="C:\\music\\my band"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
          style={{ minWidth: 320 }}
        />
        <button
          disabled={!!busy || !folder.trim()}
          onClick={() =>
            run("import", () =>
              api.importFolder(bandId!, {
                path: folder.trim(),
                recursive: true,
                auto_approve: false,
              }),
            )
          }
        >
          {busy === "import" ? "importing…" : "Import folder"}
        </button>
        <button disabled={!!busy} onClick={() => run("analyze", () => api.analyzeBand(bandId!))}>
          {busy === "analyze" ? "analysing…" : "Analyse all"}
        </button>
        <label>
          <input
            type="file"
            style={{ display: "none" }}
            onChange={(e) =>
              e.target.files?.[0] &&
              run("upload", async () => {
                await api.uploadReference(bandId!, e.target.files![0]);
                return {};
              })
            }
          />
          <span className="pill" style={{ cursor: "pointer" }}>
            + single file
          </span>
        </label>
      </div>

      {dna && (
        <div className="ab">
          <strong>DNA</strong> —{" "}
          {(dna.references as { analyzed?: number })?.analyzed ?? 0} analysed ·{" "}
          {Math.round((dna.references as { total_seconds?: number })?.total_seconds ?? 0)}s ·{" "}
          {bpm?.mean ? `BPM ${bpm.min}–${bpm.max} (avg ${bpm.mean})` : "no BPM"} ·{" "}
          keys: {Object.entries(keyDist).map(([k, n]) => `${k}×${n}`).join(", ") || "—"}
        </div>
      )}

      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>BPM</th>
            <th>Key</th>
            <th>Tuning</th>
            <th>Quality</th>
            <th>Train</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {refs.map((r) => (
            <tr key={r.id}>
              <td>{r.title}</td>
              <td>
                <span className="pill">{r.analysis_status}</span>
              </td>
              <td>{r.bpm ?? "—"}</td>
              <td>{r.key ?? "—"}</td>
              <td className="muted">{r.tuning ?? "—"}</td>
              <td>
                {r.quality_json ? (
                  <span title={r.quality_json.flags.join("; ")}>
                    {r.quality_json.score.toFixed(2)}
                    {r.quality_json.passed ? "" : " ⚠"}
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td>
                <input
                  type="checkbox"
                  checked={r.approved_for_training}
                  disabled={r.analysis_status !== "ready"}
                  onChange={() => toggleApprove(r)}
                />
              </td>
              <td>
                <button className="danger" onClick={() => run("del", async () => {
                  await api.deleteReference(r.id);
                  return {};
                })}>
                  delete
                </button>
              </td>
            </tr>
          ))}
          {refs.length === 0 && (
            <tr>
              <td colSpan={8} className="muted">
                no references yet
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <h2>Training manifest</h2>
      {manifest?.status === 409 ? (
        <div className="ab">
          <strong className="danger">Incomplete</strong> — approved references missing metadata:
          <ul>
            {(
              (manifest.body as { detail: { incomplete: { title: string; missing: string[] }[] } })
                .detail.incomplete
            ).map((x, i) => (
              <li key={i}>
                {x.title}: {x.missing.join(", ")}
              </li>
            ))}
          </ul>
        </div>
      ) : manifest?.status === 200 ? (
        <div className="ab">
          <div>
            dataset_version <code>{(manifest.body as { dataset_version: string }).dataset_version}</code>{" "}
            · {(manifest.body as { totals: { count: number } }).totals.count} references
          </div>
          {((manifest.body as { warnings: string[] }).warnings ?? []).map((w, i) => (
            <div key={i} className="muted">
              ⚠ {w}
            </div>
          ))}
          <div className="row">
            <button
              disabled={!!busy}
              onClick={() =>
                run("snap", async () => {
                  const s = await api.snapshotManifest(bandId!);
                  alert(`saved ${s.path}\ndataset_version ${s.dataset_version}`);
                  return {};
                })
              }
            >
              Snapshot manifest to file
            </button>
          </div>
        </div>
      ) : null}

      <h2>Band adapters</h2>
      <p className="muted">
        An adapter distils the approved Band DNA into character / tempo / key priors.
        The music provider conditions on it when generating a section instrumental.
      </p>
      <div className="row">
        <button
          disabled={!!busy || manifest?.status !== 200}
          onClick={() =>
            run("train", () => api.trainAdapter(bandId!, "band"))
          }
        >
          {busy === "train" ? "training…" : "Train band adapter"}
        </button>
        {manifest?.status !== 200 && (
          <span className="muted">approve references and resolve the manifest first</span>
        )}
      </div>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Provider</th>
            <th>dataset_version</th>
            <th>Character</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {adapters.map((a) => {
            const ch = (a.spec_json.character ?? {}) as Record<string, number>;
            return (
              <tr key={a.id}>
                <td>{a.name}</td>
                <td className="muted">{a.provider_version}</td>
                <td>
                  <code>{a.dataset_version ?? "—"}</code>
                </td>
                <td className="muted">
                  {Object.entries(ch)
                    .map(([k, v]) => `${k} ${v.toFixed(2)}`)
                    .join(" · ") || "—"}
                </td>
                <td>
                  <button
                    className="danger"
                    onClick={() =>
                      run("del", async () => {
                        await api.deleteAdapter(a.id);
                        return {};
                      })
                    }
                  >
                    delete
                  </button>
                </td>
              </tr>
            );
          })}
          {adapters.length === 0 && (
            <tr>
              <td colSpan={5} className="muted">
                no adapters yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
