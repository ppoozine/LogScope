import { LibraryOverviewView } from "@/components/library/library-overview-view";

type SearchParams = { status?: string; q?: string };

export default async function LibraryPage(props: { searchParams: Promise<SearchParams> }) {
  const sp = await props.searchParams;
  return (
    <div className="mx-auto max-w-screen-2xl px-6 py-6">
      <LibraryOverviewView initialFilters={sp} />
    </div>
  );
}
