# 09 — End-to-end QA and polish

**Type:** human-in-the-loop
**Blocked by:** 08
**Blocks:** none

## Goal
Run end-to-end tests with a real client (eastofengland) to validate the pipeline runs successfully with typed config, and create follow-up tickets for any issues found.

## Vertical slice
- **Integration test:** Run the full pipeline test suite to ensure all consumers work correctly with typed config
- **Manual QA:** Test with eastofengland client end-to-end to validate pipeline runs with actual Snowflake connections
- **Validation:** Confirm Pydantic validation errors are clear and actionable for operators
- **Type checking:** Verify type hints work correctly across the codebase (IDE autocomplete, mypy if used)
- **Documentation review:** Ensure all docs are accurate and complete

## Acceptance
- Full pipeline test suite passes
- Manual eastofengland test run succeeds
- Config validation errors produce clear, actionable messages
- IDE autocomplete works for all config fields
- All documentation is accurate and consistent
- Any issues found are documented as follow-up tickets

## Notes
- This is the final QA step after all code changes are complete
- Use the real eastofengland client config for manual testing
- Test with both valid and invalid configs to verify validation works
- Check that type hints provide good IDE experience
- Create follow-up tickets for any bugs or improvements discovered
- This issue type is human-in-the-loop because it requires judgment on what constitutes a blocker vs. polish
