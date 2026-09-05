import { useState } from "react";
import { ExternalLink, FileSearch, Loader2, Upload } from "lucide-react";
import { lookupExif } from "../lib/api.js";
import { Card, Field, LookupHeader, Pill } from "../components/LookupKit.jsx";

export default function FileMeta() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [drag, setDrag] = useState(false);

  async function onFile(file) {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      setData(await lookupExif(file));
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      <LookupHeader
        icon={FileSearch}
        kicker="File Meta"
        title="EXIF and PDF properties"
        blurb="Drop a photo or PDF. Camera, timestamps, and GPS if the file still has them. Parsed in memory and discarded."
      />

      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          onFile(e.dataTransfer.files?.[0]);
        }}
        className={`flex flex-col items-center justify-center gap-2 min-h-36 rounded-lg border border-dashed px-4 py-6 cursor-pointer ${
          drag ? "border-matrix bg-matrix/5 text-matrix" : "border-zinc-700 bg-zinc-950/60 text-zinc-400"
        }`}
      >
        {loading ? <Loader2 className="h-5 w-5 animate-spin text-matrix" /> : <Upload className="h-5 w-5" />}
        <span className="text-[12px] font-mono">Drop JPEG / PNG / WebP / TIFF / PDF — 8 MB max</span>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,image/tiff,application/pdf,.jpg,.jpeg,.png,.webp,.tif,.tiff,.pdf"
          className="sr-only"
          onChange={(e) => onFile(e.target.files?.[0])}
        />
      </label>

      {error && <p className="text-[12px] font-mono text-rose-400">{error}</p>}

      {data && (
        <Card className="max-w-xl">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[13px] text-zinc-100 truncate">{data.filename}</h3>
            <Pill ok label={data.kind} />
          </div>
          <Field label="size" value={`${data.size_bytes} bytes`} />
          <Field label="format" value={data.format} />
          <Field label="pixels" value={data.width ? `${data.width}×${data.height}` : null} />
          <Field label="pages" value={data.pages} />
          <Field label="camera" value={[data.camera_make, data.camera_model].filter(Boolean).join(" ")} />
          <Field label="software" value={data.software} />
          <Field label="taken" value={data.taken_at} />
          <Field label="title" value={data.title} />
          <Field label="author" value={data.author} />
          <Field label="creator" value={data.creator} />
          <Field label="producer" value={data.producer} />
          <Field label="created" value={data.created} />
          <Field
            label="gps"
            value={data.gps ? `${data.gps.latitude}, ${data.gps.longitude}` : null}
          />
          {data.map?.osm && (
            <a
              href={data.map.osm}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[10px] font-mono text-matrix"
            >
              Open GPS pin <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <p className="text-[10px] text-zinc-600 pt-1">{data.note}</p>
        </Card>
      )}
    </div>
  );
}
