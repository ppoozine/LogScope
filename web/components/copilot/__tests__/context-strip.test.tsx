import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { ContextStrip } from "@/components/copilot/context-strip";
import { useCopilotStore } from "@/lib/copilot/store";

describe("<ContextStrip>", () => {
  beforeEach(() => {
    useCopilotStore.setState({ pageContext: null });
  });

  it("renders nothing when pageContext is null", () => {
    const { container } = render(<ContextStrip />);
    expect(container.firstChild).toBeNull();
  });

  it("renders analyzer pills (D1 baseline)", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: "a\nb",
        vrlEngine: null,
        logs: ["x"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<ContextStrip />);
    expect(screen.getByText(/VRL 2 行/)).toBeInTheDocument();
    expect(screen.getByText(/1 筆 logs/)).toBeInTheDocument();
  });

  it("renders analyzer match candidate pill", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: [],
        parseResults: [],
        matchTopCandidate: {
          vendorSlug: "paloalto",
          productSlug: "pan-os",
          logTypeName: "traffic",
          confidence: 0.94,
        },
      },
    });
    render(<ContextStrip />);
    expect(screen.getByText(/paloalto\/pan-os/)).toBeInTheDocument();
    expect(screen.getByText(/94%/)).toBeInTheDocument();
  });

  it("renders library_overview pills", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "library_overview",
        filters: { status: "published", q: undefined },
        vendorCount: 5,
        productCount: 12,
        productsMissingParseRule: ["v/p1", "v/p2"],
      },
    });
    render(<ContextStrip />);
    expect(screen.getByText(/5 vendors/)).toBeInTheDocument();
    expect(screen.getByText(/12 products/)).toBeInTheDocument();
    expect(screen.getByText(/2 個未建庫/)).toBeInTheDocument();
    expect(screen.getByText(/status=published/)).toBeInTheDocument();
  });

  it("renders library_product pills", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "library_product",
        vendorSlug: "paloalto",
        productSlug: "pan-os",
        productStatus: "active",
        activeLogType: {
          name: "traffic",
          fields: [
            { name: "src_ip", type: "string", required: true },
            { name: "dst_ip", type: "string", required: true },
          ],
          samplesCount: 5,
          parseRuleHead: null,
        },
      },
    });
    render(<ContextStrip />);
    expect(screen.getByText(/paloalto\/pan-os/)).toBeInTheDocument();
    expect(screen.getByText(/active/)).toBeInTheDocument();
    expect(screen.getByText(/log_type: traffic/)).toBeInTheDocument();
    expect(screen.getByText(/2 fields/)).toBeInTheDocument();
  });

  it("renders library_versions pills with diff", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "library_versions",
        vendorSlug: "p",
        productSlug: "x",
        logTypeName: "t",
        diff: {
          baseVersion: "v3",
          headVersion: "v4",
          baseVrl: null,
          headVrl: null,
        },
      },
    });
    render(<ContextStrip />);
    expect(screen.getByText(/p\/x/)).toBeInTheDocument();
    expect(screen.getByText("t")).toBeInTheDocument();
    expect(screen.getByText(/v3 → v4/)).toBeInTheDocument();
  });

  it("renders library_versions without diff pill when diff is null", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "library_versions",
        vendorSlug: "p",
        productSlug: "x",
        logTypeName: "t",
        diff: null,
      },
    });
    render(<ContextStrip />);
    expect(screen.queryByText(/v\d → v\d/)).toBeNull();
  });
});
