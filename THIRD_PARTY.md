# Third-party software and notices

ClassicVoice is MIT-licensed; see [LICENSE](LICENSE). Windows builds include the unmodified components below. Their license texts and required notices are copied into the installed `licenses` directory. Source archives for the bundled GPL components are included there as well.

## Speech engines

| Component | Version / use | License and source |
| --- | --- | --- |
| eSpeak NG | 1.52.0 executable, shared library and voice data; classic speech and Kokoro phonemization | GPL-3.0-or-later. [Upstream release](https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0); full license and corresponding source archive are shipped in `licenses/`. |
| Kokoro 82M model and voice pack | Quantized ONNX model and preset voice vectors downloaded on request | Apache-2.0. [Model project](https://huggingface.co/hexgrad/Kokoro-82M) and [ONNX export release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1). The app pins each file's size and SHA-256 and places the model license beside the downloaded files. The model weights are not included in the Windows package. |
| kokoro-onnx | 0.6.1; local ONNX inference wrapper | MIT. [Source](https://github.com/thewh1teagle/kokoro-onnx); license text shipped in `licenses/`. |
| phonemizer | 3.4.0; text-to-phoneme conversion | GPL-3.0. [Source](https://github.com/bootphon/phonemizer); license and the exact 3.4.0 source archive are shipped in `licenses/`. |
| espeakng-loader | 0.2.4; phonemizer library loading | MIT. [Source](https://github.com/thewh1teagle/espeakng-loader); license text shipped in `licenses/`. |

## Python runtime dependencies for Kokoro

The Windows package contains these pinned runtime components for local neural synthesis:

| Component | Version | License / notice |
| --- | --- | --- |
| ONNX Runtime | 1.31.0 | MIT and Microsoft `ThirdPartyNotices.txt`, both shipped in `licenses/`. [Source](https://github.com/microsoft/onnxruntime) |
| NumPy | 2.4.6 | BSD-3-Clause; package license and bundled dependency notices are in `licenses/`. [Source](https://github.com/numpy/numpy) |
| FlatBuffers | 25.12.19 | Apache-2.0; see the Apache-2.0 license text shipped for the Kokoro model. [Source](https://github.com/google/flatbuffers) |
| protobuf | 7.36.2 | BSD-3-Clause; license text shipped in `licenses/`. [Source](https://github.com/protocolbuffers/protobuf) |
| packaging | 26.3 | Apache-2.0 or BSD-2-Clause; both license texts shipped in `licenses/`. [Source](https://github.com/pypa/packaging) |
| attrs | 26.1.0 | MIT; license text shipped in `licenses/`. [Source](https://github.com/python-attrs/attrs) |
| cffi | 2.1.1 | MIT-0; license text shipped in `licenses/`. [Source](https://github.com/python-cffi/cffi) |
| cloudpickle | 3.1.2 | BSD-3-Clause; license text shipped in `licenses/`. [Source](https://github.com/cloudpipe/cloudpickle) |
| dlinfo | 2.0.0 | MIT; license text shipped in `licenses/`. [Source](https://github.com/thewh1teagle/dlinfo) |
| joblib | 1.6.0 | BSD-3-Clause; license text shipped in `licenses/`. [Source](https://github.com/joblib/joblib) |
| typing-extensions | 4.16.0 | PSF-2.0; license text shipped in `licenses/`. [Source](https://github.com/python/typing_extensions) |

The model download uses GitHub only after the user chooses **Download and install**. Model inference, phonemization and WAV creation run locally. ONNX Runtime telemetry is disabled before the inference session is created. ClassicVoice does not upload text, use accounts or make background model requests.

The eSpeak NG MSI is fetched from its official GitHub release and checked against SHA-256 `7F673C709EA5DD579D3B5EBB98688CC575328A6AB7438D2BC405B88CEDAEAFB9` before extraction. The MSI is not Authenticode-signed; the pinned digest is checked before its files are used. The build extracts it without running the installer or changing machine-wide settings.

No proprietary Loquendo voices, names or branding are bundled. Anyone redistributing a combined build must preserve the notices and comply with each component's license.
