# Competitor notes (Phase 1.4)

Researched with web search on the date of this commit. These are vendor pages and secondary sources, not tests of the products. Check each vendor's current docs and pricing before you use any of this in a decision.

## Reality Defender (commercial deepfake detection)
- Sells detection through an API and SDKs, a web app, and products for call centers and meetings. Sources: [API page](https://realitydefender.com/api), [platform](https://realitydefender.com/platform), [launch coverage](https://www.securitysystemsnews.com/article/reality-defender-launches-public-api-and-free-tier).
- Launch coverage said a free tier with 50 detections a month; image and audio first, video planned. A third-party summary lists video on paid plans. Video support is unconfirmed here.
- Returns a detailed result and recommends using the "ensemble" result ([docs](https://docs.realitydefender.com/api-reference/quickstart.md)). No tamper-evident record of the verdict was mentioned.

## Hive (AI-generated content detection)
- REST API for images, video, audio and text, including a unified deepfake endpoint and a guess at which generator made the media. Sources: [docs](https://docs.thehive.ai/docs/ai-generated-content-detection), [image and video](https://docs.thehive.ai/docs/ai-image-and-video-detection).
- A third-party review lists prices and says independent benchmarks for audio and video are limited: accuracy claims are mostly the vendor's own ([review](https://fast.io/resources/hive-moderation-ai-detector-review-2026/)). Treat prices as unverified.

## C2PA / Content Credentials (provenance standard, not a detector)
- A validator checks a signed manifest, its certificate chain and that the manifest matches this file. It shows who signed claims, not that the content is true. Sources (secondary): [SoftwareSeni](https://www.softwareseni.com/how-c2pa-content-credentials-work-and-what-their-limits-are/), [Magnet Forensics](https://www.magnetforensics.com/blog/c2pa-and-media-authentication-what-you-need-to-know/).
- Credentials are often stripped by messaging apps and re-encoding. A missing manifest proves nothing, and a manipulated file can carry a valid one.
- The official specification page did not appear in the results: read it at c2pa.org before you rely on this summary.

## What this means for AuthentiTrace (hypothesis, not proven)
- **Gap the product can fill:** detectors return a score and leave you to trust it; C2PA proves origin only when credentials survive. AuthentiTrace combines both (C2PA when present, detection when not) and adds a tamper-evident record of each verdict, an explicit "cannot tell" outcome, and a human review trail. None of the sources above mention a verifiable verdict log.
- **Where it is weaker today:** its detectors are rule-based, with no published accuracy; the vendors above have trained models (their accuracy is also vendor-reported).
- **Reasonable position:** integrate rather than compete on raw detection: allow a vendor API as one more signal, and compete on the record, the review workflow and the abstain behavior.

One-line edge to test with real buyers: "Every verdict comes with a proof you can check yourself, and the system says when it does not know."
