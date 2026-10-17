"""Static admin page. It contains no data and no secrets; every action needs the admin key typed into the page."""

HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Red-team target admin</title>
<style>
body{font:16px system-ui,sans-serif;max-width:34rem;margin:3rem auto;padding:0 1rem;color:#1a1a1a}
input,button{font:inherit;padding:.6rem .8rem;width:100%;box-sizing:border-box;margin:.4rem 0}
button{background:#1f4fd8;color:#fff;border:0;border-radius:6px;cursor:pointer}button:disabled{opacity:.5;cursor:not-allowed}
dl{display:grid;grid-template-columns:auto 1fr;gap:.3rem 1rem}dt{color:#555}#msg{min-height:1.5rem}.err{color:#b00020}.ok{color:#0a6b2d}
</style></head><body>
<h1>Prepare next scan</h1>
<p>Enter the admin key, click <b>Prepare next scan</b> once, wait for the new run ID, then start the scan.
The dataset stays unchanged until you click again.</p>
<label for="k">Admin API key (kept in this page only)</label>
<input id="k" type="password" autocomplete="off">
<button id="go">Prepare next scan</button>
<p id="msg" role="status"></p>
<dl><dt>Run ID</dt><dd id="run">-</dd><dt>Dataset ID</dt><dd id="ds">-</dd><dt>Record count</dt><dd id="n">-</dd><dt>Seed</dt><dd id="seed">-</dd></dl>
<script>
const $=id=>document.getElementById(id);
function show(d,note){$("run").textContent=d.run_id;$("ds").textContent=d.dataset_id;$("n").textContent=d.record_count;$("seed").textContent=d.seed;
  $("msg").className="ok";$("msg").textContent=note;}
$("go").addEventListener("click",async()=>{
  const key=$("k").value.trim(); if(!key){$("msg").className="err";$("msg").textContent="Enter the admin key.";return;}
  const b=$("go"); b.disabled=true; $("msg").className="";$("msg").textContent="Rotating...";
  try{ // one request per click; never retried automatically
    const r=await fetch("/admin/reset",{method:"POST",headers:{"Authorization":"Bearer "+key,"Content-Type":"application/json"},body:"{}"});
    const d=await r.json();
    if(!r.ok){$("msg").className="err";$("msg").textContent=r.status==401?"Invalid admin key.":"Failed: "+(d.detail||r.status);}
    else show(d,"Dataset rotated. You can start the scan now.");
  }catch(e){$("msg").className="err";$("msg").textContent="Request failed; state unknown. Check the run ID with the manifest before clicking again.";}
  finally{b.disabled=false;}
});
</script></body></html>"""
