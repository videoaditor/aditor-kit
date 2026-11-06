// Edit Kit native helper (macOS frameworks only, no installs).
//   kit mask IN.mp4 W H        -> raw gray8 person mask frames on stdout (pipe into ffmpeg)
//   kit focus CLIP.mp4 SEC     -> "x y w h" (0..1, top-left origin) of what the eye goes to in that frame
//   kit captions JOB.json DIR  -> one transparent PNG per caption, all the same size: [{"text","file","w","h","size"}]
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

struct Cap: Decodable { let text: String; let file: String; let w: Int; let h: Int; let size: Double }

func captions(_ jsonPath: String, _ dir: String) {
    guard let data = FileManager.default.contents(atPath: jsonPath),
          let caps = try? JSONDecoder().decode([Cap].self, from: data) else { fail("bad \(jsonPath)") }
    for c in caps {
        let font = NSFont(name: "SFProDisplay-Black", size: c.size) ?? NSFont.systemFont(ofSize: c.size, weight: .black)
        let para = NSMutableParagraphStyle(); para.alignment = .center
        let fill: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: NSColor.white, .paragraphStyle: para]
        var stroke = fill; stroke[.foregroundColor] = NSColor.black
        stroke[.strokeColor] = NSColor.black; stroke[.strokeWidth] = 30.0   // outline drawn under the fill
        let s = NSAttributedString(string: c.text, attributes: fill)
        let h = c.h, th = ceil(s.boundingRect(with: NSSize(width: CGFloat(c.w) - 40, height: 2000), options: [.usesLineFragmentOrigin]).height)
        let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: c.w, pixelsHigh: h, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                   isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
        let r = NSRect(x: 20, y: (CGFloat(h) - th) / 2, width: CGFloat(c.w) - 40, height: th)   // vertically centred
        NSAttributedString(string: c.text, attributes: stroke).draw(with: r, options: [.usesLineFragmentOrigin])
        s.draw(with: r, options: [.usesLineFragmentOrigin])
        NSGraphicsContext.restoreGraphicsState()
        try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: dir + "/" + c.file))
    }
}

let a = CommandLine.arguments
switch a.count > 1 ? a[1] : "" {
case "mask" where a.count == 5: mask(a[2], Int(a[3])!, Int(a[4])!)
case "focus" where a.count == 4: focus(a[2], Double(a[3])!)
case "captions" where a.count == 4: captions(a[2], a[3])
default: fail("usage: kit mask IN W H | kit focus CLIP SEC | kit captions JOB.json DIR")
}
