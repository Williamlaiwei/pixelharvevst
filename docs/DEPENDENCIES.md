# Dependency license inventory

`dependency-licenses.json` records installed package names, versions, declared licenses and project links from distribution metadata. It includes runtime/browser/development/build dependencies used for validation, excluding this project's MIT license and the standalone lock-generation tool. The complete inventory is more informative than claiming the project has only MIT dependencies.

Observed declarations include MIT/CMU, BSD variants, Apache-2.0, PSF-2.0 and MPL-2.0, plus bundled-license expressions in numerical/image packages. In particular certifi declares MPL-2.0; NumPy declares several bundled-component licenses; Playwright declares Apache-2.0. Some packages use broad metadata labels such as "BSD License", so metadata alone is not a complete redistribution review. Preserve upstream notices and review the installed distribution's license files if redistributing dependencies or binaries.

No dependency source or binary is vendored into this repository. Dependencies are installed from separately distributed packages. Browser binaries are downloaded separately by Playwright and are outside this Python package inventory. The owner approved release of the project code under MIT. That license does not supersede upstream licenses or cover separately distributed dependencies/browser binaries.

This is a metadata inventory and publication checklist, not a legal opinion or dependency vulnerability audit. The owner approval and publication scope are recorded in the release review.
