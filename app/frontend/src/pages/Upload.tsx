import { useState } from "react";
import { uploadCsv } from "../api/orders";

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<{ created: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await uploadCsv(file);
      setResult(res);
    } catch {
      setError("Upload failed. Please check the file format and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-4">Upload Orders CSV</h1>

      <div className="bg-white border rounded p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <p className="text-sm text-gray-600 mb-2">
              Upload a CSV file with columns:{" "}
              <code className="text-xs bg-gray-100 px-1 rounded">
                external_id, customer_name, item_name, price, quantity
              </code>
            </p>
            {/* BUG F7: file input has no aria-label and no associated <label> */}
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>

          <button
            type="submit"
            disabled={!file || loading}
            className="w-full bg-blue-600 text-white py-2 rounded font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Uploading…" : "Upload"}
          </button>
        </form>

        {result && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 text-green-800 rounded text-sm">
            Successfully created {result.created} orders.
          </div>
        )}

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">
            {error}
          </div>
        )}
      </div>

      <div className="mt-4 text-sm text-gray-500">
        <p className="font-medium mb-1">Note:</p>
        <p>
          Re-uploading the same file will create duplicate orders — each row is
          inserted without checking for existing records.
        </p>
      </div>
    </div>
  );
}
