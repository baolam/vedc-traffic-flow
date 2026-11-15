"""Thư viện nhỏ để sinh file .drawio (mxGraph XML, không nén) có nhiều trang.

Chỉ dùng để dựng bản đầu. Sau khi đội đã sửa file .drawio thì file đó là bản gốc,
đừng chạy lại script sinh hình, vì sẽ ghi đè lên chỉnh sửa của đội.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from xml.sax.saxutils import escape, quoteattr

FONT = "Helvetica"

# Bảng màu theo tầng (fill, stroke). Dùng chung cho cả 4 hình để người đọc nhận ra tầng.
TIER = {
    "world": ("#F4F4F2", "#6B6B66"),
    "edge_ai": ("#EAF2FB", "#2563A8"),
    "network": ("#FFF5E1", "#B7791F"),
    "control": ("#F2EEFA", "#6B46C1"),
    "actuate": ("#E9F6EE", "#2F7D4F"),
    "safety": ("#FDEDED", "#C0392B"),
    "power": ("#FFF1E6", "#C05621"),
    "shared": ("#F7F7F7", "#8A8A8A"),
}

FLOW = {
    "observe": "#2563A8",   # telemetry / quan sát
    "command": "#6B46C1",   # lệnh điều khiển
    "feedback": "#2F7D4F",  # ACK, health
    "power": "#C05621",
    "physical": "#6B6B66",
    "planned": "#9A9A9A",
}


def label(title: str, sub: str | None = None, mono: str | None = None,
          title_size: int = 13, sub_size: int = 11) -> str:
    """Nhãn HTML: dòng tiêu đề đậm, dòng phụ nhạt, dòng mono (tên file/topic)."""
    parts = [f'<b style="font-size:{title_size}px">{title}</b>']
    if sub:
        parts.append(f'<span style="font-size:{sub_size}px;color:#4A4A4A">{sub}</span>')
    if mono:
        parts.append(f'<span style="font-size:{sub_size - 1}px;font-family:Menlo,Consolas,monospace;'
                     f'color:#555555">{mono}</span>')
    return "<br>".join(parts)


def style(**kw) -> str:
    return ";".join(f"{k}={v}" for k, v in kw.items()) + ";"


def box_style(tier: str, *, dashed: bool = False, white: bool = True, size: int = 12,
              align: str = "center", rounded: bool = True, bold: bool = False, extra: dict | None = None) -> str:
    fill, stroke = TIER[tier]
    kw = dict(rounded=1 if rounded else 0, arcSize=8, whiteSpace="wrap", html=1,
              fillColor="#FFFFFF" if white else fill, strokeColor=stroke, strokeWidth=1.4,
              fontFamily=FONT, fontSize=size, align=align, verticalAlign="middle",
              spacingLeft=8, spacingRight=8, fontColor="#1F1F1F")
    if dashed:
        kw.update(dashed=1, dashPattern="6 4")
    if bold:
        kw["fontStyle"] = 1
    if extra:
        kw.update(extra)
    return style(**kw)


def container_style(tier: str, *, size: int = 14, dashed: bool = False) -> str:
    fill, stroke = TIER[tier]
    kw = dict(rounded=1, arcSize=3, whiteSpace="wrap", html=1, container=1, collapsible=0,
              recursiveResize=0, fillColor=fill, strokeColor=stroke, strokeWidth=1.8,
              fontFamily=FONT, fontSize=size, fontStyle=1, fontColor=stroke,
              align="left", verticalAlign="top", spacingLeft=14, spacingTop=8)
    if dashed:
        kw.update(dashed=1, dashPattern="8 5")
    return style(**kw)


def edge_style(flow: str, *, dashed: bool = False, both: bool = False, width: float = 1.8,
               size: int = 11, curved: bool = False, end: str = "block", extra: dict | None = None) -> str:
    color = FLOW[flow]
    kw = dict(edgeStyle="orthogonalEdgeStyle", rounded=1, orthogonalLoop=1, jettySize="auto", html=1,
              strokeColor=color, strokeWidth=width, endArrow=end, endFill=1, endSize=7,
              fontFamily=FONT, fontSize=size, fontColor=color, labelBackgroundColor="#FFFFFF",
              spacing=2)
    if curved:
        kw.pop("edgeStyle")
        kw["curved"] = 1
    if both:
        kw.update(startArrow=end, startFill=1, startSize=7)
    if dashed:
        kw.update(dashed=1, dashPattern="6 4")
    if extra:
        kw.update(extra)
    return style(**kw)


@dataclass
class Page:
    name: str
    width: int
    height: int
    cells: list[str] = field(default_factory=list)
    _ids: set[str] = field(default_factory=set)

    def _new_id(self, cid: str) -> str:
        if cid in self._ids:
            raise ValueError(f"trùng id: {cid}")
        self._ids.add(cid)
        return cid

    def vertex(self, cid: str, x: float, y: float, w: float, h: float, value: str, sty: str,
               parent: str = "1") -> str:
        cid = self._new_id(cid)
        self.cells.append(
            f'<mxCell id={quoteattr(cid)} value={quoteattr(value)} style={quoteattr(sty)} '
            f'vertex="1" parent={quoteattr(parent)}>'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return cid

    def text(self, cid: str, x: float, y: float, w: float, h: float, value: str, *, size: int = 12,
             color: str = "#1F1F1F", align: str = "left", bold: bool = False, parent: str = "1") -> str:
        sty = style(text=1, html=1, whiteSpace="wrap", fontFamily=FONT, fontSize=size, fontColor=color,
                    align=align, verticalAlign="middle", fontStyle=1 if bold else 0,
                    strokeColor="none", fillColor="none")
        return self.vertex(cid, x, y, w, h, value, sty, parent)

    def edge(self, cid: str, src: str, tgt: str, value: str, sty: str, *,
             points: list[tuple[float, float]] | None = None,
             exit_: tuple[float, float] | None = None, entry: tuple[float, float] | None = None,
             label_pos: float | None = None, label_offset: tuple[float, float] | None = None) -> str:
        cid = self._new_id(cid)
        if exit_:
            sty += f"exitX={exit_[0]};exitY={exit_[1]};exitDx=0;exitDy=0;"
        if entry:
            sty += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
        geo_attr = ""
        if label_pos is not None:
            geo_attr += f' x="{label_pos}"'
        geo_inner = ""
        if label_offset is not None:
            geo_inner += f'<mxPoint x="{label_offset[0]}" y="{label_offset[1]}" as="offset"/>'
        if points:
            pts = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in points)
            geo_inner += f'<Array as="points">{pts}</Array>'
        self.cells.append(
            f'<mxCell id={quoteattr(cid)} value={quoteattr(value)} style={quoteattr(sty)} edge="1" '
            f'parent="1" source={quoteattr(src)} target={quoteattr(tgt)}>'
            f'<mxGeometry{geo_attr} relative="1" as="geometry">{geo_inner}</mxGeometry></mxCell>')
        return cid

    def free_edge(self, cid: str, p1: tuple[float, float], p2: tuple[float, float], value: str, sty: str) -> str:
        """Đoạn thẳng không gắn shape (dùng cho chú giải)."""
        cid = self._new_id(cid)
        self.cells.append(
            f'<mxCell id={quoteattr(cid)} value={quoteattr(value)} style={quoteattr(sty)} edge="1" parent="1">'
            f'<mxGeometry relative="1" as="geometry">'
            f'<mxPoint x="{p1[0]}" y="{p1[1]}" as="sourcePoint"/>'
            f'<mxPoint x="{p2[0]}" y="{p2[1]}" as="targetPoint"/></mxGeometry></mxCell>')
        return cid

    def table(self, cid: str, x: float, y: float, col_widths: list[int], rows: list[list[str]],
              *, row_h: int = 30, header_fill: str = "#EDEDED", size: int = 11,
              mono_cols: tuple[int, ...] = ()) -> None:
        """Bảng dựng bằng ô chữ nhật rời, đội dễ sửa từng ô."""
        cy = y
        for r, row in enumerate(rows):
            cx = x
            for c, (txt, w) in enumerate(zip(row, col_widths)):
                is_head = r == 0
                font = "Menlo" if (c in mono_cols and not is_head) else FONT
                sty = style(rounded=0, whiteSpace="wrap", html=1, fontFamily=font,
                            fontSize=size - (1 if font == "Menlo" else 0),
                            fillColor=header_fill if is_head else "#FFFFFF", strokeColor="#BDBDBD",
                            align="left", verticalAlign="middle", spacingLeft=8, spacingRight=6,
                            fontStyle=1 if is_head else 0, fontColor="#1F1F1F")
                self.vertex(f"{cid}_r{r}c{c}", cx, cy, w, row_h, escape(txt) if font == "Menlo" else txt, sty)
                cx += w
            cy += row_h

    def xml(self, page_id: str) -> str:
        body = "".join(self.cells)
        return (f'<diagram id={quoteattr(page_id)} name={quoteattr(self.name)}>'
                f'<mxGraphModel dx="0" dy="0" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
                f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{self.width}" '
                f'pageHeight="{self.height}" background="#FFFFFF" math="0" shadow="0">'
                f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{body}</root></mxGraphModel></diagram>')


def write_drawio(path: str, pages: list[Page]) -> None:
    diagrams = "".join(p.xml(f"page-{i + 1}") for i, p in enumerate(pages))
    xml = (f'<mxfile host="drawio" agent="EdgeFlow AI report generator" version="24.0.0">'
           f'{diagrams}</mxfile>\n')
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
