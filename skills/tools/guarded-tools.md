# Guarded Tools

Local-First tools should be deliberately narrow.

- Read-only tools are allowed first.
- Write tools must produce a preview before changing files.
- Shell tools stay disabled until the operator enables them.
- Destructive shell patterns require a hard deny, not a softer warning.
- Tool outputs should be captured as evidence when they influence a decision.
