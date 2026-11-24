# Dependency license inventory

`dependency-licenses.json` records installed package names, versions, declared licenses and project links from distribution metadata. It includes runtime/browser/development/build dependencies used for validation, excluding this project's pending owner-approved license and the standalone lock-generation tool. The complete inventory is more informative than claiming the project has only MIT dependencies.

Observed declarations include MIT/CMU, BSD variants, Apache-2.0, PSF-2.0 and MPL-2.0, plus bundled-license expressions in numerical/image packages. In particular certifi declares MPL-2.0; NumPy declares several bundled-component licenses; Playwright declares Apache-2.0. Some packages use broad metadata labels such as "BSD License", so metadata alone is not a complete redistribution review. Preserve upstream notices and review the installed distribution's license files if redistributing dependencies or binaries.

No dependency source or binary is vendored into this repository. Dependencies are installed from separately distributed packages. Browser binaries are downloaded separately by Playwright and are outside this Python package inventory. An effective project license can be chosen only for code the owner has the right to license. The proposed MIT file does not supersede upstream licenses or establish ownership.

This is a metadata inventory and publication checklist, not a legal opinion or dependency vulnerability audit. Outstanding owner confirmation is recorded in the release review.
