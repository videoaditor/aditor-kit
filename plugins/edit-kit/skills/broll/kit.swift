// Edit Kit native helper (macOS frameworks only, no installs).
//   kit mask IN.mp4 W H        -> raw gray8 person mask frames on stdout (pipe into ffmpeg)
//   kit focus CLIP.mp4 SEC     -> "x y w h" (0..1, top-left origin) of what the eye goes to in that frame
//   kit captions JOB.json DIR  -> one transparent PNG per caption, all the same size (style fields: see struct Cap)
import AVFoundation
import AppKit
import CoreImage
import Vision

func fail(_ s: String) -> Never { FileHandle.standardError.write((s + "\n").data(using: .utf8)!); exit(1) }

func mask(_ path: String, _ W: Int, _ H: Int) {
    let asset = AVURLAsset(url: URL(fileURLWithPath: path))
    guard let track = asset.tracks(withMediaType: .video).first, let reader = try? AVAssetReader(asset: asset) else { fail("cannot read \(path)") }
    let out = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
    reader.add(out); reader.startReading()
    let req = VNGeneratePersonSegmentationRequest()
    req.qualityLevel = .balanced
    req.outputPixelFormat = kCVPixelFormatType_OneComponent8
    let ctx = CIContext(options: [.workingColorSpace: NSNull()])
    var buf = [UInt8](repeating: 0, count: W * H)
    let stdout = FileHandle.standardOutput
    while let sample = out.copyNextSampleBuffer(), let px = CMSampleBufferGetImageBuffer(sample) {
        try? VNImageRequestHandler(cvPixelBuffer: px, options: [:]).perform([req])
        buf.withUnsafeMutableBytes { $0.initializeMemory(as: UInt8.self, repeating: 0) }
        if let m = req.results?.first?.pixelBuffer {
            let img = CIImage(cvPixelBuffer: m)
            let scaled = img.transformed(by: CGAffineTransform(scaleX: CGFloat(W) / img.extent.width, y: CGFloat(H) / img.extent.height))
            buf.withUnsafeMutableBytes { ctx.render(scaled, toBitmap: $0.baseAddress!, rowBytes: W, bounds: CGRect(x: 0, y: 0, width: W, height: H), format: .L8, colorSpace: nil) }
        }
        stdout.write(Data(buf))
    }
}

func focus(_ path: String, _ sec: Double) {
    let gen = AVAssetImageGenerator(asset: AVURLAsset(url: URL(fileURLWithPath: path)))
    gen.appliesPreferredTrackTransform = true
    guard let img = try? gen.copyCGImage(at: CMTime(seconds: sec, preferredTimescale: 600), actualTime: nil) else { fail("no frame") }
    let req = VNGenerateAttentionBasedSaliencyImageRequest()
    try? VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    let boxes = (req.results?.first?.salientObjects ?? []).map { $0.boundingBox }
    let u = boxes.reduce(boxes.first ?? CGRect(x: 0.25, y: 0.25, width: 0.5, height: 0.5)) { $0.union($1) }
    print(String(format: "%.3f %.3f %.3f %.3f", u.minX, 1 - u.maxY, u.width, u.height))   // Vision is bottom-left origin
}

struct Cap: Decodable {
    let text: String; let file: String; let w: Int; let h: Int
    let font: String; let size: Double; let color: String
    let stroke: String?; let strokeW: Double?          // outline colour + width (% of font size)
    let shadow: Bool?                                   // soft drop shadow
    let box: String?; let radius: Double?               // rounded box behind each line (TikTok text bubble)
    let hl: [Int]?; let hlColor: String?; let hlMode: String?   // highlighted word indices, "box" or "text"
    let reply: String?                                  // TikTok comment-reply sticker: commenter name, text = comment
}

func drawReply(_ c: Cap, _ name: String) -> CGImage {
    let W = c.w, H = c.h, fs = CGFloat(c.size)
    let cg = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                       bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    cg.translateBy(x: 0, y: CGFloat(H)); cg.scaleBy(x: 1, y: -1)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(cgContext: cg, flipped: true)
    let small: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: fs * 0.52, weight: .regular), .foregroundColor: hex("#8A8A8E")]
    let big: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: fs, weight: .bold), .foregroundColor: hex("#161616")]
    let head = NSAttributedString(string: "Reply to \(name)'s comment", attributes: small)
    let maxText = CGFloat(W) - fs * 3.6
    let body = NSAttributedString(string: c.text, attributes: big)
    let bb = body.boundingRect(with: NSSize(width: maxText, height: 2000), options: [.usesLineFragmentOrigin])
    let hb = head.boundingRect(with: NSSize(width: maxText, height: 200), options: [.usesLineFragmentOrigin])
    let av = fs * 1.5, padX = fs * 0.55, padY = fs * 0.45
    let cardW = padX * 2 + av + fs * 0.4 + max(bb.width, hb.width), cardH = padY * 2 + hb.height + bb.height + fs * 0.1
    let card = NSRect(x: (CGFloat(W) - cardW) / 2, y: (CGFloat(H) - cardH) / 2, width: cardW, height: cardH)
    let sh = NSShadow(); sh.shadowColor = NSColor.black.withAlphaComponent(0.25); sh.shadowBlurRadius = fs * 0.4
    sh.set(); NSColor.white.setFill(); NSBezierPath(roundedRect: card, xRadius: fs * 0.35, yRadius: fs * 0.35).fill()
    NSShadow().set()
    hex("#C9C9CE").setFill()
    NSBezierPath(ovalIn: NSRect(x: card.minX + padX, y: card.minY + padY, width: av, height: av)).fill()
    let tx = card.minX + padX + av + fs * 0.4
    head.draw(with: NSRect(x: tx, y: card.minY + padY, width: maxText, height: hb.height), options: [.usesLineFragmentOrigin])
    body.draw(with: NSRect(x: tx, y: card.minY + padY + hb.height + fs * 0.1, width: maxText, height: bb.height), options: [.usesLineFragmentOrigin])
    NSGraphicsContext.restoreGraphicsState()
    return cg.makeImage()!
}

func savePNG(_ img: CGImage, _ path: String) {
    let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: path) as CFURL, "public.png" as CFString, 1, nil)!
    CGImageDestinationAddImage(dest, img, nil); CGImageDestinationFinalize(dest)
}

func hex(_ s: String) -> NSColor {
    var v: UInt64 = 0; Scanner(string: s.replacingOccurrences(of: "#", with: "")).scanHexInt64(&v)
    return NSColor(srgbRed: CGFloat((v >> 16) & 255) / 255, green: CGFloat((v >> 8) & 255) / 255, blue: CGFloat(v & 255) / 255, alpha: 1)
}

func font(_ name: String, _ size: Double) -> NSFont {
    if name == "serif", let d = NSFont.systemFont(ofSize: size, weight: .medium).fontDescriptor.withDesign(.serif) {
        return NSFont(descriptor: d, size: size)!
    }
    return NSFont(name: name, size: size) ?? NSFont.systemFont(ofSize: size, weight: .heavy)
}

func captions(_ jsonPath: String, _ dir: String) {
    guard let data = FileManager.default.contents(atPath: jsonPath),
          let caps = try? JSONDecoder().decode([Cap].self, from: data) else { fail("bad \(jsonPath)") }
    for c in caps {
        if let name = c.reply { savePNG(drawReply(c, name), dir + "/" + c.file); continue }
        let W = c.w, H = c.h, pad: CGFloat = 40
        let para = NSMutableParagraphStyle(); para.alignment = .center; para.lineHeightMultiple = 0.95
        let base: [NSAttributedString.Key: Any] = [.font: font(c.font, c.size), .foregroundColor: hex(c.color), .paragraphStyle: para]
        let storage = NSTextStorage(string: c.text, attributes: base)
        // word index -> character range (for highlights)
        var ranges: [NSRange] = []
        let ns = c.text as NSString
        ns.enumerateSubstrings(in: NSRange(location: 0, length: ns.length), options: .byWords) { _, r, _, _ in ranges.append(r) }
        let hl = (c.hl ?? []).filter { $0 < ranges.count }.map { ranges[$0] }
        if c.hlMode == "text", let col = c.hlColor { for r in hl { storage.addAttribute(.foregroundColor, value: hex(col), range: r) } }
        if c.hlMode != "text", let col = c.hlColor {                          // dark word on a light block, white on a dark one
            let k = hex(col).usingColorSpace(.sRGB)!
            let light = 0.2126 * k.redComponent + 0.7152 * k.greenComponent + 0.0722 * k.blueComponent > 0.6
            for r in hl { storage.addAttribute(.foregroundColor, value: light ? hex("#111111") : NSColor.white, range: r) }
        }
        let lm = NSLayoutManager(), tc = NSTextContainer(size: NSSize(width: CGFloat(W) - 2 * pad, height: 4000))
        tc.lineFragmentPadding = 0; lm.addTextContainer(tc); storage.addLayoutManager(lm)
        let used = lm.usedRect(for: tc)
        let origin = NSPoint(x: pad, y: (CGFloat(H) - used.height) / 2)

        let cg = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                           bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        cg.translateBy(x: 0, y: CGFloat(H)); cg.scaleBy(x: 1, y: -1)            // top-left origin, like the layout manager
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(cgContext: cg, flipped: true)
        let all = lm.glyphRange(for: tc)
        let fs = CGFloat(c.size)
        if let b = c.box {                                                     // one rounded box per line
            hex(b).setFill()
            lm.enumerateLineFragments(forGlyphRange: all) { _, usedLine, _, _, _ in
                let r = usedLine.offsetBy(dx: origin.x, dy: origin.y).insetBy(dx: -fs * 0.35, dy: -fs * 0.08)
                NSBezierPath(roundedRect: r, xRadius: CGFloat(c.radius ?? 12), yRadius: CGFloat(c.radius ?? 12)).fill()
            }
        }
        if c.hlMode != "text", let col = c.hlColor {                          // coloured box behind the key word
            hex(col).setFill()
            for r in hl {
                let g = lm.glyphRange(forCharacterRange: r, actualCharacterRange: nil)
                // tight per-word rect: x from glyph positions, y from the line fragment
                let line = lm.lineFragmentRect(forGlyphAt: g.location, effectiveRange: nil)     // glyph x is relative to this
                let usedLine = lm.lineFragmentUsedRect(forGlyphAt: g.location, effectiveRange: nil)
                let x0 = line.minX + lm.location(forGlyphAt: g.location).x
                let endG = NSMaxRange(g)
                let x1 = endG < lm.numberOfGlyphs && lm.lineFragmentRect(forGlyphAt: endG, effectiveRange: nil).minY == line.minY
                    ? line.minX + lm.location(forGlyphAt: endG).x : usedLine.maxX
                let rect = NSRect(x: x0, y: line.minY, width: x1 - x0, height: line.height)
                    .offsetBy(dx: origin.x, dy: origin.y).insetBy(dx: -fs * 0.12, dy: -fs * 0.02)
                NSBezierPath(roundedRect: rect, xRadius: fs * 0.12, yRadius: fs * 0.12).fill()
            }
        }
        if let st = c.stroke {                                                 // outline pass under the fill
            let full = NSRange(location: 0, length: storage.length)
            let saved = storage.attributedSubstring(from: full)
            storage.addAttributes([.strokeColor: hex(st), .strokeWidth: c.strokeW ?? 8, .foregroundColor: hex(st)], range: full)
            if c.hlMode != "text" && c.hlColor != nil { for r in hl { storage.addAttributes([.strokeWidth: 0, .foregroundColor: NSColor.clear], range: r) } }
            lm.drawGlyphs(forGlyphRange: all, at: origin)
            storage.setAttributedString(saved)
        }
        if c.shadow == true {
            let sh = NSShadow(); sh.shadowColor = NSColor.black.withAlphaComponent(0.75)
            sh.shadowBlurRadius = fs * 0.18; sh.shadowOffset = NSSize(width: 0, height: -fs * 0.04)
            storage.addAttribute(.shadow, value: sh, range: NSRange(location: 0, length: storage.length))
        }
        lm.drawGlyphs(forGlyphRange: all, at: origin)
        NSGraphicsContext.restoreGraphicsState()
        savePNG(cg.makeImage()!, dir + "/" + c.file)
    }
}

let a = CommandLine.arguments
switch a.count > 1 ? a[1] : "" {
case "mask" where a.count == 5: mask(a[2], Int(a[3])!, Int(a[4])!)
case "focus" where a.count == 4: focus(a[2], Double(a[3])!)
case "captions" where a.count == 4: captions(a[2], a[3])
default: fail("usage: kit mask IN W H | kit focus CLIP SEC | kit captions JOB.json DIR")
}
