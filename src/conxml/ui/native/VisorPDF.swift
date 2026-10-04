import AppKit
import PDFKit

final class Visor: NSObject, NSApplicationDelegate {
    let url: URL
    let documento: PDFDocument
    let pdf = PDFView()
    var ventana: NSWindow!
    let indice = NSTextField(labelWithString: "")

    init(url: URL, documento: PDFDocument) {
        self.url = url
        self.documento = documento
    }

    func boton(_ texto: String, _ accion: Selector) -> NSButton {
        let b = NSButton(title: texto, target: self, action: accion)
        b.bezelStyle = .rounded
        return b
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        ventana = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 800),
            styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        ventana.title = "ConXml — Vista previa PDF"
        ventana.minSize = NSSize(width: 700, height: 480)
        ventana.isReleasedWhenClosed = false
        let contenido = ventana.contentView!
        let espacio = NSView()
        espacio.setContentHuggingPriority(.defaultLow, for: .horizontal)
        let barra = NSStackView(views: [boton("Anterior", #selector(anterior)), indice,
            boton("Siguiente", #selector(siguiente)), boton("−", #selector(reducir)),
            boton("+", #selector(ampliar)), boton("Ajustar", #selector(ajustar)), espacio,
            boton("Guardar PDF…", #selector(guardar))])
        barra.orientation = .horizontal
        barra.spacing = 8
        barra.translatesAutoresizingMaskIntoConstraints = false
        pdf.translatesAutoresizingMaskIntoConstraints = false
        contenido.addSubview(barra)
        contenido.addSubview(pdf)
        NSLayoutConstraint.activate([
            barra.topAnchor.constraint(equalTo: contenido.topAnchor, constant: 12),
            barra.leadingAnchor.constraint(equalTo: contenido.leadingAnchor, constant: 12),
            barra.trailingAnchor.constraint(equalTo: contenido.trailingAnchor, constant: -12),
            pdf.topAnchor.constraint(equalTo: barra.bottomAnchor, constant: 12),
            pdf.leadingAnchor.constraint(equalTo: contenido.leadingAnchor),
            pdf.trailingAnchor.constraint(equalTo: contenido.trailingAnchor),
            pdf.bottomAnchor.constraint(equalTo: contenido.bottomAnchor)])
        pdf.document = documento
        pdf.displayMode = .singlePageContinuous
        pdf.displayDirection = .vertical
        pdf.autoScales = true
        pdf.minScaleFactor = 0.25
        pdf.maxScaleFactor = 8
        NotificationCenter.default.addObserver(self, selector: #selector(actualizar), name: .PDFViewPageChanged, object: pdf)
        actualizar()
        ventana.center()
        ventana.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func actualizar() {
        let pagina = pdf.currentPage.map { documento.index(for: $0) + 1 } ?? 1
        indice.stringValue = "Página \(pagina) de \(documento.pageCount)"
    }
    @objc func anterior() { pdf.goToPreviousPage(nil) }
    @objc func siguiente() { pdf.goToNextPage(nil) }
    @objc func ampliar() { pdf.autoScales = false; pdf.zoomIn(nil) }
    @objc func reducir() { pdf.autoScales = false; pdf.zoomOut(nil) }
    @objc func ajustar() { pdf.autoScales = true }
    @objc func guardar() {
        let panel = NSSavePanel()
        panel.title = "Guardar PDF"
        panel.allowedFileTypes = ["pdf"]
        panel.nameFieldStringValue = url.lastPathComponent
        panel.beginSheetModal(for: ventana) { respuesta in
            guard respuesta == .OK, let destino = panel.url else { return }
            do { try Data(contentsOf: self.url).write(to: destino, options: .atomic) }
            catch {
                let alerta = NSAlert(error: error)
                alerta.beginSheetModal(for: self.ventana)
            }
        }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

guard CommandLine.arguments.count == 2 else { exit(2) }
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let documento = PDFDocument(url: url), documento.pageCount > 0 else { exit(3) }
let delegado = Visor(url: url, documento: documento)
let app = NSApplication.shared
app.setActivationPolicy(.regular)
app.delegate = delegado
app.run()
