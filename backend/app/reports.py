from datetime import datetime
from sqlalchemy import func, select
from .models import DeviceStatusLog, Ticket


def _pdf(lines: list[str]) -> bytes:
    # Minimal standards-compliant PDF, deliberately dependency-free for reports.
    content = "BT /F1 12 Tf 50 760 Td " + " Tj 0 -18 Td ".join("(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")" for line in lines) + " Tj ET"
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>", "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", f"<< /Length {len(content.encode())} >>\nstream\n{content}\nendstream"]
    output = b"%PDF-1.4\n"; offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(output)); output += f"{i} 0 obj\n{obj}\nendobj\n".encode()
    start = len(output); output += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    output += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return output + f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()


async def monthly_report(session) -> bytes:
    total = await session.scalar(select(func.count(Ticket.id))) or 0
    open_count = await session.scalar(select(func.count(Ticket.id)).where(Ticket.status != "RESOLVED")) or 0
    down = await session.scalar(select(func.count(DeviceStatusLog.id)).where(DeviceStatusLog.status == "DOWN")) or 0
    return _pdf(["OIC NetRadar Management Report", f"Generated: {datetime.utcnow().isoformat()} UTC", f"Total incidents: {total}", f"Open incidents: {open_count}", f"Recorded DOWN events: {down}", "Uptime and MTTR require a production reporting window and resolved tickets."])
