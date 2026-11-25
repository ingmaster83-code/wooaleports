# -*- coding: utf-8 -*-
"""우아레포츠 정적 사이트 생성기.
입력: data/list.json.gz(레포츠 목록, 캠핑 AC05 제외) · data/details/*.json.gz(이용시간·요금·휴무 등, TourAPI 필드 원래 이름) · data/lcls_codes.json(분류체계 이름)
출력: _site/ (시설 상세, 종목·지역 허브, 안내, 검색 인덱스, sitemap). 상세 없는 시설은 만들지 않는다. 상세 30곳 미만이면 noindex '준비 중' 홈만 배포.
"""
import collections, gzip, html as ihtml, json, os, re, shutil, sys
from datetime import datetime, timedelta, timezone

from common import *  # noqa

sys.stdout.reconfigure(encoding="utf-8")
DATA = pathlib.Path(os.environ["DATA_DIR"]) if os.environ.get("DATA_DIR") else ROOT / "data"
TODAY = (datetime.now(timezone.utc) + timedelta(hours=9)).date()

SHORT = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
         "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원", "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전라북도": "전북", "전라남도": "전남",
         "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주", "전남광주통합특별시": "전남광주"}
# 분류체계 코드 → 종목 묶음
GROUP = {}
for c, g in (("LS010400", "골프"), ("LS020500", "낚시"), ("LS020600", "낚시"), ("LS010800", "스키·눈썰매"), ("LS011000", "스키·눈썰매"), ("LS010900", "스케이트"), ("LS010700", "승마"),
             ("LS020100", "수상레저"), ("LS020200", "수상레저"), ("LS020300", "수상레저"), ("LS020400", "수상레저"), ("LS020700", "수상레저"), ("LS020800", "수상레저"), ("LS021100", "수상레저"), ("LS021400", "수상레저"),
             ("LS030100", "항공레저"), ("LS030200", "항공레저"), ("LS030300", "항공레저"), ("LS030400", "항공레저"), ("LS030600", "항공레저"),
             ("LS010100", "체험레저"), ("LS010200", "체험레저"), ("LS010300", "체험레저"), ("LS011200", "체험레저"), ("LS011300", "체험레저"), ("LS011500", "체험레저"), ("LS011800", "체험레저"), ("LS010500", "체험레저"), ("LS010600", "체험레저"),
             ("LS011600", "체험레저"), ("VE100100", "체육시설"), ("VE100200", "체육시설"), ("LS040100", "복합레저"), ("VE050200", "복합레저"), ("LS011900", "걷기·기타 체험")):
    GROUP[c] = g
GSLUG = {"골프": "골프", "낚시": "낚시", "스키·눈썰매": "스키눈썰매", "스케이트": "스케이트", "승마": "승마", "수상레저": "수상레저", "항공레저": "항공레저", "체험레저": "체험레저", "체육시설": "체육시설", "복합레저": "복합레저", "걷기·기타 체험": "걷기체험"}
# 상세 필드 후보(TourAPI 레포츠 소개정보, 원래 이름)
FIELDS = [("ut", "이용 시간", ("usetimeleports", "usetime")), ("fee", "이용 요금", ("usefeeleports", "usefee")), ("rest", "쉬는 날", ("restdateleports", "restdate")),
          ("op", "개장 기간", ("openperiod", "opendate")), ("rv", "예약 안내", ("reservation",)), ("pk", "주차", ("parkingleports", "parking")), ("pf", "주차 요금", ("parkingfeeleports", "parkingfee")),
          ("ag", "체험 가능 연령", ("expagerangeleports", "expagerange")), ("ac", "수용 인원", ("accomcountleports", "accomcount")), ("sc", "규모", ("scaleleports", "scale")), ("ic", "문의 전화", ("infocenterleports", "infocenter"))]


def un(s):
    return ihtml.unescape(ihtml.unescape(s or ""))


def plain(s):
    s = un(s)
    s = re.sub(r"<br\s*/?>|</p>|\\n", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[ \t ]+", " ", s.replace("\r", ""))
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def one(s):
    return re.sub(r"\s+", " ", plain(s)).strip()


def cut(s, n):
    return s if len(s) <= n else s[:n].rstrip(" ,/·") + "…"


def region_of(addr):
    t = (addr or "").split()
    if not t:
        return "", ""
    sido = SHORT.get(t[0], "")
    if not sido:
        return "", ""
    if sido == "세종":
        return sido, "세종시"
    return sido, (t[1] if len(t) > 1 and re.search(r"(시|군|구)$", t[1]) else "")


def load():
    rows = json.loads(gzip.open(DATA / "list.json.gz", "rt", encoding="utf-8").read())
    codes = {x["lclsSystm3Cd"]: x["lclsSystm3Nm"] for x in json.loads((ROOT / "data" / "lcls_codes.json").read_text(encoding="utf-8"))}
    det = {}
    for p in (DATA / "details").glob("*.json.gz"):
        det.update(json.loads(gzip.open(p, "rt", encoding="utf-8").read()))
    ps = []
    for r in rows:
        d = det.get(r["id"])
        grp = GROUP.get(r["c3"], "")
        if not d or not grp:
            continue
        name = un(r["t"]).strip()
        vals = {}
        for k, label, keys in FIELDS:
            for kk in keys:
                v = one(d.get(kk))
                if v and v not in ("-", "없음"):
                    vals[k] = v
                    break
        if not name or not any(k in vals for k in ("ut", "fee", "rest", "op", "rv", "pk", "ag", "ac", "sc")):
            continue
        sido, sgg = region_of(r["a"])
        if not sido:
            continue
        ps.append(dict(id=r["id"], name=name, addr=(r["a"] + (" " + r["a2"] if r["a2"] else "")).strip(), sido=sido, sgg=sgg, x=r["x"], y=r["y"], mod=r["mod"], grp=grp, sub=codes.get(r["c3"], ""), v=vals))
    return ps, len(rows)


def plink(p):
    return '<a href="/place/%s/">%s</a>' % (p["id"], esc(p["name"]))


def ptable(L, cap=150, region=True):
    L = L[:cap]
    head = "<tr><th>시설</th>%s<th>종목</th><th>이용 시간</th><th>이용 요금</th></tr>" % ("<th>지역</th>" if region else "")
    rows = []
    for p in L:
        rows.append("<tr><td>%s</td>%s<td>%s</td><td>%s</td><td>%s</td></tr>" % (plink(p), ("<td>%s</td>" % esc((p["sido"] + " " + p["sgg"]).strip())) if region else "", esc(p["sub"] or p["grp"]), esc(cut(p["v"].get("ut", "-"), 22)), esc(cut(p["v"].get("fee", "-"), 22))))
    return '<div class="tbl-wrap"><table class="tbl">%s%s</table></div>' % (head, "".join(rows))


def stat(L):
    tc = collections.Counter(p["grp"] for p in L)
    s = "이용 시간·요금 등 정보가 등록된 레포츠 시설 <b>%d곳</b>입니다." % len(L)
    if tc:
        s += " " + ", ".join("%s %d곳" % (k, v) for k, v in tc.most_common(4)) + " 순으로 많습니다."
    return '<p class="lead">%s</p>' % s


def hub(path, h1, sub, L, extra="", cap=150, title=None, desc=None, crumbs=None, prio="0.7", region=True, faq=None):
    body = ['<div class="page-head"><h1>%s</h1><p>%s</p></div>' % (esc(h1), esc(sub)), stat(L), ad(), extra, '<h2 class="group-title">시설 목록</h2>', ptable(L, cap, region)]
    if len(L) > cap:
        body.append('<p class="note">시설이 많아 %d곳만 표시했습니다. 종목·지역별 페이지에서 좁혀 보세요.</p>' % cap)
    write(path, layout(path, title or h1, desc or sub, "\n".join(b for b in body if b), faq, crumbs or [("홈", "/")], coupang=True), prio)


def page_place(p, by_sgg, hubs_ok):
    region = (p["sido"] + " " + p["sgg"]).strip()
    kind = p["sub"] or p["grp"]
    v = p["v"]
    lead = ["<b>%s</b>은(는) %s에 있는 %s 시설입니다." % (esc(p["name"]), esc(region), esc(kind))]
    if v.get("ut"):
        lead.append("이용 시간은 %s%s." % (esc(cut(v["ut"], 80)), "이고" if v.get("fee") else "입니다"))
    if v.get("fee"):
        lead.append("이용 요금은 %s입니다." % esc(cut(v["fee"], 100)))
    rows = [("종목", kind)] + [(label, v[k]) for k, label, _ in FIELDS if k in v] + [("주소", p["addr"])]
    tbl = '<div class="tbl-wrap"><table class="tbl">%s</table></div>' % "".join("<tr><th>%s</th><td>%s</td></tr>" % (a, esc(cut(b, 500))) for a, b in rows if b)
    body = ['<div class="page-head"><h1>%s</h1><p>%s</p></div>' % (esc(p["name"]), esc(" · ".join(x for x in (region, kind) if x))), '<p class="lead">%s</p>' % " ".join(lead), ad(), tbl]
    if p["x"] and p["y"]:
        body.append('<p><a class="btn" href="https://map.kakao.com/link/map/%s,%s,%s">🗺️ 지도에서 위치 보기</a></p>' % (urllib.parse.quote(p["name"][:40]), p["y"], p["x"]))
    body.append('<div class="note-box">시설 정보는 한국관광공사 TourAPI(공공데이터포털) 기준이며, 이용 시간·요금·휴무·예약 방법은 바뀔 수 있습니다. 방문 전에 시설에 확인하세요.</div>')
    sib = [o for o in by_sgg.get((p["sido"], p["sgg"]), []) if o is not p and o["grp"] == p["grp"]][:8]
    if len(sib) < 8:
        sib += [o for o in by_sgg.get((p["sido"], p["sgg"]), []) if o is not p and o not in sib][:8 - len(sib)]
    if sib:
        body.append('<h2 class="group-title">같은 지역 다른 시설 <small>%s</small></h2>' % esc(region))
        body.append(ptable(sib, 8, False))
    chips = []
    if ("region", p["sido"]) in hubs_ok:
        chips.append('<a class="chip" href="/region/%s/">%s 레포츠</a>' % (q(p["sido"]), esc(p["sido"])))
    if p["sgg"] and ("sgg", p["sido"], p["sgg"]) in hubs_ok:
        chips.append('<a class="chip" href="/region/%s/%s/">%s %s 레포츠</a>' % (q(p["sido"]), q(p["sgg"]), esc(p["sido"]), esc(p["sgg"])))
    if ("ts", p["grp"], p["sido"]) in hubs_ok:
        chips.append('<a class="chip" href="/type/%s/%s/">%s %s</a>' % (q(GSLUG[p["grp"]]), q(p["sido"]), esc(p["sido"]), esc(p["grp"])))
    if chips:
        body.append('<div class="chips">%s</div>' % "".join(chips))
    faq = []
    if v.get("ut"):
        faq.append(("%s의 이용 시간은 어떻게 되나요?" % p["name"], "공공데이터에는 %s로 등록돼 있습니다. 계절·날씨에 따라 달라질 수 있어 방문 전에 확인하세요." % cut(v["ut"], 200)))
    if v.get("fee"):
        faq.append(("%s의 이용 요금은 얼마인가요?" % p["name"], "등록된 요금 안내는 다음과 같습니다. %s" % cut(v["fee"], 250)))
    if v.get("rest"):
        faq.append(("%s의 쉬는 날은 언제인가요?" % p["name"], "쉬는 날은 %s로 등록돼 있습니다." % cut(v["rest"], 150)))
    if v.get("rv"):
        faq.append(("%s은(는) 예약이 필요한가요?" % p["name"], cut(v["rv"], 250)))
    crumbs = [("홈", "/"), (p["sido"], "/region/%s/" % p["sido"]), ((p["name"][:26] + "…") if len(p["name"]) > 26 else p["name"], "/place/%s/" % p["id"])]
    ld = [{"@context": "https://schema.org", "@type": "SportsActivityLocation", "name": p["name"], "address": p["addr"]}]
    if v.get("ut"):
        ld[0]["openingHours"] = cut(v["ut"], 80)
    if p["x"] and p["y"]:
        ld[0]["geo"] = {"@type": "GeoCoordinates", "latitude": p["y"], "longitude": p["x"]}
    title = "%s 이용시간·요금 - %s %s" % (p["name"], region, kind)
    desc = "%s(%s %s) %s%s." % (p["name"], region, kind, ("이용시간 %s" % cut(v["ut"], 30)) if v.get("ut") else "", (", 요금 %s" % cut(v["fee"], 30)) if v.get("fee") else "")
    write("/place/%s/" % p["id"], layout("/place/%s/" % p["id"], title, desc, "\n".join(body), faq or None, crumbs, "article", ld, coupang=True), "0.6")


def build():
    ps, total_rows = load()
    print("시설", len(ps), "/ 목록", total_rows)
    OUT.mkdir(parents=True, exist_ok=True)
    for ch in OUT.iterdir():
        shutil.rmtree(ch) if ch.is_dir() else ch.unlink()
    if len(ps) < 30:
        write("/", layout("/", "레포츠 정보 수집 중 | 우아레포츠", "한국관광공사 레포츠 정보를 수집하고 있습니다.", '<div class="page-head"><h1>우아레포츠 — 준비 중</h1><p>한국관광공사 레포츠 시설 정보를 매일 조금씩 수집하고 있어요. 곧 이용시간·요금·휴무로 골프장·스키장·낚시터 등을 찾을 수 있습니다.</p></div>', None, None, noindex=True), sitemap=False)
        finish()
        return
    ps.sort(key=lambda p: (-int(p["mod"] or 0), p["id"]))
    by_sido, by_sgg, by_g, by_gs = (collections.defaultdict(list) for _ in range(4))
    for p in ps:
        by_sido[p["sido"]].append(p)
        if p["sgg"]:
            by_sgg[(p["sido"], p["sgg"])].append(p)
        by_g[p["grp"]].append(p)
        by_gs[(p["grp"], p["sido"])].append(p)
    hubs_ok = {("region", s) for s in by_sido} | {("sgg", s, g) for (s, g), L in by_sgg.items() if len(L) >= 3} | {("type", t) for t, L in by_g.items() if len(L) >= 5} \
        | {("ts", t, s) for (t, s), L in by_gs.items() if len(L) >= 3 and len(by_g[t]) >= 5}
    for p in ps:
        page_place(p, by_sgg, hubs_ok)
    for s, L in by_sido.items():
        gc = collections.Counter(p["sgg"] for p in L if p["sgg"])
        tc = collections.Counter(p["grp"] for p in L)
        extra = '<h2 class="group-title">종목별</h2><div class="chips">%s</div>' % "".join(
            ('<a class="chip" href="/type/%s/%s/">%s <small>%d</small></a>' % (q(GSLUG[t]), q(s), esc(t), n)) if ("ts", t, s) in hubs_ok else '<span class="chip">%s <small>%d</small></span>' % (esc(t), n) for t, n in tc.most_common())
        if gc:
            extra += '<h2 class="group-title">시군구별</h2><div class="chips">%s</div>' % "".join(
                ('<a class="chip" href="/region/%s/%s/">%s <small>%d</small></a>' % (q(s), q(g), esc(g), n)) if n >= 3 else '<span class="chip">%s <small>%d</small></span>' % (esc(g), n) for g, n in gc.most_common(80))
        hub("/region/%s/" % s, "%s 레포츠 시설 %d곳 - 이용시간·요금" % (s, len(L)), "지역 레포츠 시설의 이용 시간과 요금", L, extra, 150, "%s 레포츠 시설 %d곳 - 이용시간·요금·휴무" % (s, len(L)),
            "%s 골프장·낚시터·스키장 등 레포츠 시설 %d곳의 이용시간, 요금, 휴무, 예약 안내를 정리했습니다." % (s, len(L)), [("홈", "/"), ("지역별", "/region/"), (s, "/region/%s/" % s)], "0.8")
    for (s, g), L in by_sgg.items():
        if len(L) >= 3:
            hub("/region/%s/%s/" % (s, g), "%s %s 레포츠 시설 %d곳" % (s, g, len(L)), "이용시간·요금·휴무", L, "", 150, "%s %s 레포츠 시설 %d곳 - 이용시간·요금" % (s, g, len(L)),
                "%s %s의 레포츠 시설 %d곳의 이용 시간과 요금을 정리했습니다." % (s, g, len(L)), [("홈", "/"), (s, "/region/%s/" % s), (g, "/region/%s/%s/" % (s, g))], "0.6", region=False)
    cards = "".join('<a class="card" href="/region/%s/"><b>%s</b><span>%d곳</span></a>' % (q(s), esc(s), len(L)) for s, L in sorted(by_sido.items(), key=lambda t: -len(t[1])))
    write("/region/", layout("/region/", "지역별 레포츠 시설", "시도별 골프장·낚시터·스키장 등 레포츠 시설의 이용 시간과 요금을 확인하세요.", '<div class="page-head"><h1>지역별 레포츠 시설</h1></div>' + ad() + '<div class="card-grid">%s</div>' % cards, None, [("홈", "/"), ("지역별", "/region/")]), "0.8")
    for t, L in by_g.items():
        if len(L) < 5:
            continue
        sc = collections.Counter(p["sido"] for p in L)
        extra = '<h2 class="group-title">지역별</h2><div class="chips">%s</div>' % "".join(
            ('<a class="chip" href="/type/%s/%s/">%s <small>%d</small></a>' % (q(GSLUG[t]), q(s), esc(s), n)) if n >= 3 else '<span class="chip">%s <small>%d</small></span>' % (esc(s), n) for s, n in sc.most_common())
        hub("/type/%s/" % GSLUG[t], "%s %d곳 - 지역별 이용시간·요금" % (t, len(L)), "%s 시설 목록" % t, L, extra, 150, "%s 시설 %d곳 - 지역별 이용시간·요금·휴무" % (t, len(L)),
            "%s 시설 %d곳을 지역별로 정리했습니다. 이용 시간, 요금, 휴무일, 예약 안내를 확인하세요." % (t, len(L)), [("홈", "/"), ("종목별", "/type/"), (t, "/type/%s/" % GSLUG[t])], "0.8")
        for s, n in sc.items():
            if n >= 3:
                L2 = by_gs[(t, s)]
                hub("/type/%s/%s/" % (GSLUG[t], s), "%s %s %d곳" % (s, t, len(L2)), "이용시간·요금·휴무", L2, "", 150, "%s %s %d곳 - 이용시간·요금" % (s, t, len(L2)),
                    "%s의 %s 시설 %d곳의 이용 시간과 요금을 정리했습니다." % (s, t, len(L2)), [("홈", "/"), (t, "/type/%s/" % GSLUG[t]), (s, "/type/%s/%s/" % (GSLUG[t], s))], "0.6", region=False)
    cards = "".join('<a class="card" href="/type/%s/"><b>%s</b><span>%d곳</span></a>' % (q(GSLUG[t]), esc(t), len(L)) for t, L in sorted(by_g.items(), key=lambda x: -len(x[1])) if len(L) >= 5)
    write("/type/", layout("/type/", "종목별 레포츠 시설", "골프·낚시·스키·승마·수상레저 등 종목별로 시설을 찾으세요.", '<div class="page-head"><h1>종목별 레포츠 시설</h1></div>' + ad() + '<div class="card-grid">%s</div>' % cards, None, [("홈", "/"), ("종목별", "/type/")]), "0.8")
    body = ['<div class="hero"><h1>이용시간·요금으로 찾는 레포츠 시설</h1><p>한국관광공사 공공데이터의 레포츠 시설 %s곳을 종목·지역별로 찾으세요</p>'
            '<div class="today-box"><div><small>등록 시설</small><b>%s곳</b></div><div><small>종목</small><b>%d개</b></div><div><small>시군구</small><b>%d곳</b></div></div></div>' % (
                "{:,}".format(len(ps)), "{:,}".format(len(ps)), sum(1 for L in by_g.values() if len(L) >= 5), len(by_sgg)),
            '<div class="search-box"><input id="q" type="search" placeholder="시설 검색 (예: 가평 낚시터, 평창 스키장)" autocomplete="off"><div id="sr" class="sr-list"></div></div>', ad(),
            '<h2 class="group-title">종목별</h2><div class="card-grid">%s</div>' % cards,
            '<h2 class="group-title">지역별</h2><div class="card-grid">%s</div>' % "".join('<a class="card" href="/region/%s/"><b>%s</b><span>%d곳</span></a>' % (q(s), esc(s), len(L)) for s, L in sorted(by_sido.items(), key=lambda t: -len(t[1]))),
            '<h2 class="group-title">최근 갱신된 시설</h2>', ptable(ps[:10], 10), '<script src="/assets/js/search.js"></script>']
    faq = [("시설 정보는 어디서 가져왔나요?", "한국관광공사가 공공데이터포털에 공개한 TourAPI 레포츠 정보를 정리했습니다. 이용 시간·요금·휴무는 사업자가 등록한 값입니다."),
           ("캠핑장도 있나요?", "캠핑장은 우아캠프에서 따로 다룹니다. 이 사이트는 골프·낚시·스키·승마·수상레저 등 레포츠 시설 위주입니다."),
           ("예약도 할 수 있나요?", "예약을 대행하지 않고 정보만 정리합니다. 예약 방법은 각 시설 페이지의 예약 안내를 확인하세요.")]
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "우아레포츠", "url": BASE + "/", "potentialAction": {"@type": "SearchAction", "target": BASE + "/?q={q}", "query-input": "required name=q"}}]
    write("/", layout("/", "이용시간·요금으로 찾는 레포츠 시설 %s곳 | 우아레포츠" % "{:,}".format(len(ps)), "한국관광공사 공공데이터의 골프장·낚시터·스키장 등 레포츠 시설 %s곳을 이용시간·요금·휴무로 찾으세요." % "{:,}".format(len(ps)), "\n".join(body), faq, None, "website", ld), "1.0")
    idx = [[p["name"], "/place/%s/" % p["id"], p["sub"] or p["grp"], (p["sido"] + " " + p["sgg"]).strip(), ""] for p in ps]
    (OUT / "search_index.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    pages_static()
    finish()


def pages_static():
    body = ['<div class="page-head"><h1>레포츠 시설 고르는 방법과 이용 안내</h1></div>', ad(),
            '<h2 class="group-title">1. 시설 찾기</h2><ol class="lead"><li><a href="/type/">종목별</a>, <a href="/region/">지역별</a>로 후보를 좁힙니다.</li><li>시설 상세에서 이용 시간, 요금, 쉬는 날, 예약 안내를 확인합니다.</li><li>지도 버튼으로 위치를 보고, 방문 전에 시설에 최신 정보를 확인합니다.</li></ol>',
            '<h2 class="group-title">2. 정보 읽는 법</h2><ul class="lead"><li><b>이용 시간·요금</b>은 사업자가 등록한 기본 값이며 계절·날씨·성수기에 따라 달라질 수 있습니다.</li><li><b>종목 분류</b>는 한국관광공사 분류체계를 따릅니다.</li></ul>',
            '<div class="note-box">이 사이트는 공개 데이터를 정리한 참고용이며 시설의 현재 영업·예약 상태를 보장하지 않습니다. 캠핑장은 <a href="https://wooacamp.wooahouse.com">우아캠프</a>에서 확인하세요.</div>']
    write("/guide/", layout("/guide/", "레포츠 시설 고르는 방법과 이용 안내", "종목·지역별로 레포츠 시설을 찾고 이용 정보를 읽는 방법을 정리했습니다.", "\n".join(body), None, [("홈", "/"), ("이용 안내", "/guide/")]), "0.4")
    body = ['<div class="page-head"><h1>데이터 설명</h1></div>', '<p class="lead">우아레포츠는 한국관광공사 <b>TourAPI 국문 관광정보</b>(공공데이터포털)의 레포츠(콘텐츠 유형 28) 정보 중 캠핑을 제외한 시설을 정리합니다. 이용 시간·요금·쉬는 날·개장 기간·예약·주차·체험 연령·문의 전화는 사업자가 등록한 값이며, 매일 일부씩 수집해 페이지를 늘려 갑니다. 정보가 모두 비어 있는 시설은 싣지 않았고, 사진은 사용하지 않습니다.</p>']
    write("/about/", layout("/about/", "데이터 설명", "우아레포츠가 사용하는 한국관광공사 TourAPI 레포츠 데이터와 정리 방법을 설명합니다.", "\n".join(body), None, [("홈", "/"), ("데이터 설명", "/about/")]), "0.3")
    body = ['<div class="page-head"><h1>개인정보처리방침</h1></div>', '<p class="lead">우아레포츠는 회원가입·로그인 없이 이용하며 개인정보를 수집하지 않습니다. 사이트 개선을 위해 Google Analytics를 사용하고, 광고 게재를 위해 Google AdSense와 쿠팡 파트너스를 사용하며 이 과정에서 쿠키가 사용될 수 있습니다.</p>']
    write("/privacy/", layout("/privacy/", "개인정보처리방침", "우아레포츠 개인정보처리방침", "\n".join(body), None, [("홈", "/"), ("개인정보처리방침", "/privacy/")]), sitemap=False)


def finish():
    shutil.copytree(ROOT / "assets", OUT / "assets")
    for nf in ROOT.glob("naver*.html"):
        shutil.copy(nf, OUT / nf.name)
    today = TODAY.isoformat()
    urls = "".join("<url><loc>%s%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>" % (BASE, q(p), today, pr) for p, pr in WRITTEN)
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>\n' % urls, encoding="utf-8")
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % BASE, encoding="utf-8")
    (OUT / "CNAME").write_text("wooaleports.wooahouse.com\n", encoding="utf-8")
    nf = layout("/404.html", "페이지를 찾을 수 없습니다", "요청한 페이지를 찾을 수 없습니다.", '<div class="page-head"><h1>페이지를 찾을 수 없습니다</h1></div><div class="chips"><a class="chip" href="/">홈으로</a><a class="chip" href="/type/">종목별</a><a class="chip" href="/region/">지역별</a></div>', None, None, noindex=True)
    (OUT / "404.html").write_text(nf, encoding="utf-8")
    print("페이지", len(WRITTEN), "(sitemap)")


if __name__ == "__main__":
    build()
