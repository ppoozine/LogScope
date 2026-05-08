import type { components } from "@/lib/api/types";

type FieldSchemaRead = components["schemas"]["FieldSchemaRead"];

export function FieldTable({ fields }: { fields: FieldSchemaRead[] }) {
  if (fields.length === 0) {
    return (
      <section className="rounded-lg border bg-card p-4">
        <h3 className="mb-3 text-sm font-semibold">欄位</h3>
        <p className="text-xs text-muted-foreground">尚未定義欄位</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold">欄位（{fields.length}）</h3>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-left text-[10px] uppercase tracking-wider text-muted-foreground">
            <th className="py-2">名稱</th>
            <th className="py-2">型別</th>
            <th className="py-2">範例</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => (
            <tr key={field.id} className="border-b last:border-0">
              <td className="py-2">
                <span className="font-medium">{field.field_name}</span>
                {field.is_identifier && (
                  <span className="ml-2 rounded bg-purple-100 px-1.5 py-0.5 text-[9px] font-medium text-purple-700">
                    identifier
                  </span>
                )}
              </td>
              <td className="py-2 text-muted-foreground">{field.field_type}</td>
              <td className="py-2 text-muted-foreground">{field.example_value ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
