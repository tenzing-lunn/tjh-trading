# 05 — Risk Register

Home: [[PROJECT_PLAN]]

*What can hurt us, how bad, and how we mitigate. Review when anything big changes.*

| Risk | Severity | How it bites | Mitigation |
|------|----------|--------------|------------|
| **Self-deception (fake edge)** | High | We believe a curve-fit result, fund it, lose money | OOS-net-of-costs rule; verdict log; Tenzing (with the Fable audit) argues *why it's fake* before we believe it |
| **Options blow-up** | High | Naive options trade → ~−100% fast | Options paper-only until proven in 300/50 regime ([[plan/01-decision-log]]) |
| **Securities law (outside money)** | Severe (legal) | Managing/pooling strangers' money = unregistered vehicle | No outside money; Fordham ambition is research/education only |
| **Over-engineering / scope creep** | Medium | Tenzing builds features before answering "any edge?" | Roadmap "Now" stays minimal; finetune Kronos only after zero-shot edge |
| **Dirty data → fake results** | Medium | Pre-IPO junk rows, mock CSVs leak into results | Data-cleaning task; Tenzing owns the tradable universe |
| **Stale plan** | Low-Med | Knowledge base rots, becomes ignored | "Write it down same session" rule; Claude updates memory each session |
| **Optimistic cost assumptions** | Medium | Too-low costs make dead strategies look alive | Tenzing errs pessimistic; mid-price fills banned for options |
| **Real money before paper** | High | Untested strategy gets capital | 2+ weeks paper trading required before any real allocation |
