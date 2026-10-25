"""Queued Qt PDF rasterization with bounded caching and document generations."""

from collections import OrderedDict
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QSize, Signal
from PySide6.QtPdf import QPdfDocument, QPdfPageRenderer, QPdfDocumentRenderOptions

from .document import Snapshot


class PdfImages(QObject):
    image_ready = Signal()

    def __init__(self, parent=None, budget=96 * 1024 * 1024):
        super().__init__(parent)
        self.budget = budget
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.pending = {}
        self.generation = 0
        self.document = None
        self.renderer = None
        self.buffer = None

    def open(self, snapshot: Snapshot):
        # Construct a new backend before retiring the old one.
        data = QBuffer(self)
        data.setData(QByteArray(snapshot.render_bytes))
        data.open(QIODevice.OpenModeFlag.ReadOnly)
        document = QPdfDocument(self)
        document.load(data)
        if document.status() != QPdfDocument.Status.Ready or document.pageCount() != len(snapshot.pages):
            error = document.error()
            document.deleteLater()
            data.deleteLater()
            raise ValueError(f"Qt could not render this PDF ({error.name})")
        if self.renderer:
            self.renderer.setDocument(None)
            self.renderer.deleteLater()
            self.document.deleteLater()
            self.buffer.deleteLater()
        self.generation += 1
        self.document, self.buffer = document, data
        self.renderer = QPdfPageRenderer(self)
        self.renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
        self.renderer.setDocument(document)
        generation = self.generation
        self.renderer.pageRendered.connect(
            lambda page, size, image, options, request: self._complete(generation, page, size, image, request))
        self.cache.clear()
        self.pending.clear()
        self.cache_bytes = 0

    def _complete(self, generation, page, size, image, request):
        if generation != self.generation:
            return
        key = self.pending.pop(request, None)
        if key is None or image.isNull():
            return
        self.cache[key] = image
        self.cache_bytes += image.sizeInBytes()
        while self.cache_bytes > self.budget and len(self.cache) > 1:
            _, removed = self.cache.popitem(last=False)
            self.cache_bytes -= removed.sizeInBytes()
        self.image_ready.emit()

    def get(self, page, width, height, dpr=1.0):
        if self.document is None:
            return None
        # Quantization avoids a queue of almost-identical sizes during live resize.
        width = max(64, min(8192, (int(width * dpr) + 63) // 64 * 64))
        height = max(64, min(8192, (int(height * dpr) + 63) // 64 * 64))
        point = self.document.pagePointSize(page)
        scale = min(width / point.width(), height / point.height())
        size = QSize(max(1, round(point.width() * scale)), max(1, round(point.height() * scale)))
        key = (page, size.width(), size.height())
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        if key not in self.pending.values() and len(self.pending) < 12:
            options = QPdfDocumentRenderOptions()
            options.setRenderFlags(QPdfDocumentRenderOptions.RenderFlag.Annotations)
            request = self.renderer.requestPage(page, size, options)
            self.pending[request] = key
        # Use a prior resolution of the same page while a sharper image is queued.
        candidates = [(k, image) for k, image in self.cache.items() if k[0] == page]
        return max(candidates, key=lambda pair: pair[0][1])[1] if candidates else None
