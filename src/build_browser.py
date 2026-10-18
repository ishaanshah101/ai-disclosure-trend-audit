"""Build the published excerpt browser: a single self-contained HTML page that
lets a reader filter and read every corpus sentence with its year, sector,
the three passes' verdicts, the majority label, the own-use judgement and the
phrase-reuse count. Writes docs/browser.html.
"""
from __future__ import annotations
import html, json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "docs", "browser.html")


def main():
    sents = json.load(open(os.path.join(BASE, "data", "sentences.json")))
    labels = json.load(open(os.path.join(BASE, "data", "rating", "labels.json")))
    reuse = json.load(open(os.path.join(BASE, "data", "phrase_reuse.json")))
    res = json.load(open(os.path.join(BASE, "results", "analysis.json")))
    by_sid = {l["sid"]: l for l in labels.values()}
    rows = []
    for f in sents["filings"]:
        for s in f["ai_sentences"]:
            l = by_sid.get(s["id"], {})
            r = reuse.get(s["id"], {})
            rows.append({
                "id": s["id"], "y": f["year"], "co": f["name"].split("  (")[0], "sec": f["sector"],
                "t": s["text"], "na": bool(s.get("non_ai")),
                "a": l.get("class_a"), "b": l.get("class_b"), "c": l.get("class_c"),
                "m": l.get("class_majority"), "oa": l.get("own_a"), "ob": l.get("own_b"), "oc": l.get("own_c"),
                "om": l.get("own_majority"), "ru": r.get("reuse_ciks"), "ph": r.get("phrase"), "th": r.get("total_hits"),
            })
    data = json.dumps(rows, separators=(",", ":"))
    uni = res["universe"]
    n_corpus = res["corpus"]["sentences"]
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Sentence Browser</title>
<style>
:root{{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9;--card:#ffffff;
--capability:#2a78d6;--risk:#eb6834;--market:#1baf7a;--governance:#eda100;--other:#e87ba4;--accent:#2a78d6}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--line:#2c2c2a;--card:#232322}}}}
:root[data-theme="dark"]{{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--line:#2c2c2a;--card:#232322}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{padding:20px 16px 8px;max-width:1100px;margin:0 auto}}h1{{font-size:22px;margin:0 0 4px}}p.lead{{color:var(--ink2);margin:0 0 12px;max-width:80ch}}
.filters{{display:flex;flex-wrap:wrap;gap:8px;padding:8px 16px;max-width:1100px;margin:0 auto;align-items:center}}
.filters select,.filters input{{font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}}
.filters input[type=search]{{flex:1;min-width:160px}}.count{{color:var(--muted);font-size:13px;padding:0 16px;max-width:1100px;margin:0 auto}}
main{{max-width:1100px;margin:0 auto;padding:8px 16px 40px}}
.row{{border-top:1px solid var(--line);padding:10px 0;display:grid;grid-template-columns:1fr;gap:4px}}
.meta{{font-size:12.5px;color:var(--ink2);display:flex;flex-wrap:wrap;gap:10px;align-items:center}}
.tag{{display:inline-block;padding:1px 7px;border-radius:999px;font-size:12px;color:#fff}}
.tag.capability{{background:var(--capability)}}.tag.risk{{background:var(--risk)}}.tag.market{{background:var(--market)}}.tag.governance{{background:var(--governance);color:#0b0b0b}}.tag.other{{background:var(--other);color:#0b0b0b}}.tag.none{{background:var(--muted)}}
.own{{font-weight:600}}.na{{opacity:.55}}.phrase{{color:var(--muted);font-size:12px}}
.sum{{display:flex;flex-wrap:wrap;gap:14px;margin:6px 0 2px;font-size:13px;color:var(--ink2)}}
</style></head><body>
<header><h1>Every AI sentence in the sample, with its verdicts</h1>
<p class="lead">Companion page to <em>The Boilerplate Decade</em>. {n_corpus:,} sentences from 315 annual reports filed 2015 to 2026 that mention artificial intelligence, each rated twice blind, a third time where the two passes disagreed, and scored for how many other registrants have filed the same 12-word phrase. Sentences removed by the term audit (the letters AI inside a company name) are shown greyed. Source: SEC EDGAR, public domain.</p>
<div class="sum"><span>10-Ks mentioning AI: {uni['2015']['raw_share']*100:.1f}% in 2015, {uni['2025']['raw_share']*100:.1f}% in 2025</span><span>Repository: github.com/ishaanshah101/ai-disclosure-trend-audit</span></div>
</header>
<div class="filters">
<input id="q" type="search" placeholder="search text or company">
<select id="year"><option value="">all years</option>{''.join(f'<option>{y}</option>' for y in range(2015, 2027))}</select>
<select id="cls"><option value="">all classes</option><option>capability</option><option>risk</option><option>market</option><option>governance</option><option>other</option><option value="disputed">unresolved</option></select>
<select id="own"><option value="">own use: any</option><option value="1">own use: yes</option><option value="0">own use: no</option></select>
<select id="sec"><option value="">all sectors</option><option value="technology">technology</option><option value="healthcare">healthcare</option><option value="finance_realestate">finance and real estate</option><option value="other">other</option></select>
<select id="ru"><option value="">any reuse</option><option value="0">used by no other registrant</option><option value="5">flagged boilerplate (5 or more)</option><option value="30">30 or more registrants</option></select>
<label><input id="showna" type="checkbox"> show removed</label>
</div>
<div class="count" id="count"></div>
<main id="list"></main>
<script>
const DATA={data};
const $=id=>document.getElementById(id);
function render(){{
  const q=$('q').value.trim().toLowerCase(), y=$('year').value, c=$('cls').value, o=$('own').value, s=$('sec').value, ru=$('ru').value, na=$('showna').checked;
  let rows=DATA.filter(r=>{{
    if(r.na&&!na)return false;
    if(y&&String(r.y)!==y)return false;
    if(c==='disputed'){{if(r.m)return false}}else if(c&&r.m!==c)return false;
    if(o==='1'&&r.om!==true)return false; if(o==='0'&&r.om!==false)return false;
    if(s&&r.sec!==s)return false;
    if(ru==='0'&&r.ru!==0)return false; if(ru==='5'&&!(r.ru>=5))return false; if(ru==='30'&&!(r.ru>=30))return false;
    if(q&&!(r.t.toLowerCase().includes(q)||r.co.toLowerCase().includes(q)))return false;
    return true;}});
  $('count').textContent=rows.length.toLocaleString()+' sentences shown';
  const frag=document.createDocumentFragment();
  rows.slice(0,600).forEach(r=>{{
    const d=document.createElement('div'); d.className='row'+(r.na?' na':'');
    const m=r.m||'none';
    d.innerHTML=`<div class="meta"><span>${{r.y}}</span><span>${{esc(r.co)}}</span><span>${{r.sec.replace('_',' and ')}}</span>
      <span class="tag ${{m}}">${{r.na?'removed by term audit':(r.m||'unresolved')}}</span>
      <span class="own">${{r.na?'':(r.om===true?'own use: yes':(r.om===false?'own use: no':''))}}</span>
      <span>passes: ${{r.a||'-'}} / ${{r.b||'-'}}${{r.c?' / '+r.c:''}}</span>
      <span>${{r.ru==null?'':'reused by '+r.ru+' other registrant'+(r.ru===1?'':'s')}}</span></div>
      <div>${{esc(r.t)}}</div>${{r.ph?`<div class="phrase">core phrase: “${{esc(r.ph)}}”</div>`:''}}`;
    frag.appendChild(d);}});
  const list=$('list'); list.innerHTML=''; list.appendChild(frag);
  if(rows.length>600){{const p=document.createElement('p'); p.className='count'; p.textContent='Showing the first 600. Narrow the filters to see the rest.'; list.appendChild(p);}}
}}
function esc(s){{return String(s).replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]);}}
['q','year','cls','own','sec','ru','showna'].forEach(id=>$(id).addEventListener('input',render));
render();
</script></body></html>"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(page)
    print(f"-> {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
