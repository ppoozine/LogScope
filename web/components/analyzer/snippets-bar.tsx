"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useFixtures } from "@/lib/api/queries/analyzer";
import {
  type AnalyzerSnippet,
  deleteSnippet,
  loadSnippets,
  mergeSnippets,
  upsertSnippet,
} from "@/lib/storage/analyzer-snippets";

type EditorState = {
  vrl: string;
  logs: string;
  engineVersion: "0.25" | "0.32";
};

type Props = {
  current: EditorState;
  onLoad: (state: EditorState) => void;
};

export function SnippetsBar({ current, onLoad }: Props) {
  const [snippets, setSnippets] = useState<AnalyzerSnippet[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [selectedFixture, setSelectedFixture] = useState<string>("");
  const fileRef = useRef<HTMLInputElement | null>(null);
  const fixturesQuery = useFixtures();

  useEffect(() => {
    setSnippets(loadSnippets());
  }, []);

  const refresh = () => setSnippets(loadSnippets());

  const handleSelectChange = (name: string) => {
    setSelected(name);
    if (!name) return;
    const snip = snippets.find((s) => s.name === name);
    if (snip) {
      onLoad({
        vrl: snip.vrl,
        logs: snip.logs,
        engineVersion: snip.engineVersion,
      });
    }
  };

  const handleSave = () => {
    const defaultName = selected || "";
    const name = window.prompt("Snippet name:", defaultName);
    if (!name) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    upsertSnippet({
      name: trimmed,
      vrl: current.vrl,
      logs: current.logs,
      engineVersion: current.engineVersion,
      savedAt: new Date().toISOString(),
    });
    refresh();
    setSelected(trimmed);
  };

  const handleFixtureChange = (id: string) => {
    setSelectedFixture(id);
    if (!id) return;
    const fix = fixturesQuery.data?.find((f) => f.id === id);
    if (fix) {
      onLoad({
        vrl: fix.vrl,
        logs: fix.logs,
        engineVersion: fix.engine,
      });
      // Clear selection after applying so re-picking same fixture works
      setSelectedFixture("");
    }
  };

  const handleDelete = () => {
    if (!selected) return;
    if (!window.confirm(`Delete snippet "${selected}"?`)) return;
    deleteSnippet(selected);
    setSelected("");
    refresh();
  };

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(snippets, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `analyzer-snippets-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleImportClick = () => fileRef.current?.click();

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = ""; // allow re-import same file
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch (err) {
      window.alert(`Invalid JSON: ${err instanceof Error ? err.message : err}`);
      return;
    }
    try {
      const result = mergeSnippets(parsed);
      window.alert(
        `Imported ${result.total} snippet(s): ${result.added} added, ${result.replaced} replaced.`,
      );
      refresh();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Import failed");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 border-b bg-muted/20 px-6 py-1.5">
      <Label
        htmlFor="snippets-select"
        className="text-[11px] uppercase tracking-wider text-muted-foreground"
      >
        Snippets
      </Label>
      <select
        id="snippets-select"
        value={selected}
        onChange={(e) => handleSelectChange(e.target.value)}
        className="h-7 min-w-[160px] max-w-[220px] rounded-md border bg-background px-2 text-xs"
      >
        <option value="">— pick or save —</option>
        {snippets.map((s) => (
          <option key={s.name} value={s.name}>
            {s.name}
          </option>
        ))}
      </select>
      <Button
        size="sm"
        variant="ghost"
        onClick={handleSave}
        title="Save current VRL+Logs+Engine as a named snippet"
        className="h-7 text-xs"
      >
        + Save
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={handleDelete}
        disabled={!selected}
        title="Delete the selected snippet"
        className="h-7 text-xs"
      >
        Delete
      </Button>
      <span className="mx-2 h-4 w-px bg-border" />
      <Label
        htmlFor="fixtures-select"
        className="text-[11px] uppercase tracking-wider text-muted-foreground"
      >
        Fixtures
      </Label>
      <select
        id="fixtures-select"
        value={selectedFixture}
        onChange={(e) => handleFixtureChange(e.target.value)}
        disabled={fixturesQuery.isLoading || !fixturesQuery.data?.length}
        className="h-7 min-w-[160px] max-w-[220px] rounded-md border bg-background px-2 text-xs"
      >
        <option value="">— load sample —</option>
        {fixturesQuery.data?.map((f) => (
          <option key={f.id} value={f.id} title={f.description}>
            {f.name}
          </option>
        ))}
      </select>
      <span className="ml-auto flex gap-1">
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          hidden
          onChange={handleImportFile}
        />
        <Button
          size="sm"
          variant="ghost"
          onClick={handleImportClick}
          title="Import snippets from a JSON file"
          className="h-7 text-xs"
        >
          Import
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={handleExport}
          disabled={snippets.length === 0}
          title="Download all snippets as JSON"
          className="h-7 text-xs"
        >
          Export
        </Button>
      </span>
    </div>
  );
}
