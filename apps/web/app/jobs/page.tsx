"use client";

import { useEffect, useState } from "react";
import { api, type Job } from "@/lib/api";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const refresh = () => api.listJobs().then(setJobs).catch((e) => setErr(String(e)));
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <h1>Jobs</h1>
      <p className="muted">
        Every audio/ML operation is a queued job with a seed, provider version,
        logs, and output assets. Stage 0 ships one job type: a mock generation that
        writes a silent WAV.
      </p>
      {err && <p className="danger">{err}</p>}
      <div className="row">
        <button onClick={() => api.createMockJob(null).then(refresh)}>
          Queue mock generation job
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>Status</th>
            <th>Provider</th>
            <th>Progress</th>
            <th>Outputs</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id}>
              <td>{j.job_type}</td>
              <td>
                <span className="pill">{j.status}</span>
              </td>
              <td>
                {j.provider}
                {j.provider_version ? ` @ ${j.provider_version}` : ""}
              </td>
              <td>{Math.round(j.progress * 100)}%</td>
              <td>
                {j.outputs.map((o) => (
                  <div key={o.id} className="muted">
                    {o.asset_type}: {o.file_path}
                  </div>
                ))}
              </td>
            </tr>
          ))}
          {jobs.length === 0 && (
            <tr>
              <td colSpan={5} className="muted">
                no jobs yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
