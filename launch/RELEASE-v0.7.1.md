# SAM Doctor v0.7.1

SAM Doctor v0.7.1 makes multi-finding reports follow the order of the source
log. Earlier supported failures now appear before downstream rollback and
deployment noise, making the report easier to investigate in the same sequence
as the failed operation.

This is a focused compatibility release: the rule catalog, local-only behavior,
and redaction model are unchanged.
