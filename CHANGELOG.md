# Changelog

All notable changes to this project will be documented in this file.

This project uses version numbers in the `MAJOR.MINOR.PATCH` style:

- `MAJOR` — major stable changes or breaking changes
- `MINOR` — new features or notable improvements
- `PATCH` — small fixes, documentation updates, or compatibility corrections

---

## v0.2.0

Second test release.

### Added

- Full `README.md` with project description and installation notes.
- Explanation that Battery Cards works as a helper layer on top of:
  - Battery Notes for Home Assistant
  - Battery State Card
- Example dashboard files:
  - `dashboard/overall.yaml`
  - `dashboard/physical.yaml`
  - `dashboard/virtual.yaml`
- Example package file:
  - `packages/ha_batteries.yaml`
- More complete project structure for public testing.

### Changed

- Updated integration metadata for version `0.2.0`.
- Improved documentation for how the generated battery sensors are intended to be used.
- Clarified that this project is a Home Assistant helper integration, not a standalone dashboard card replacement.

---

## v0.1.0

Initial test release.

### Added

- Initial Home Assistant custom integration files.
- Basic Battery Cards sensor logic.
- Initial dashboard examples.
- Initial package example.
- Short `README.md`.

---

## Notes

Battery Cards was developed with AI assistance, while the architecture, testing, Home Assistant integration, and real-world validation were performed by the repository owner.