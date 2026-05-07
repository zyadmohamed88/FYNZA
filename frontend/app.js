"use strict";
const API="http://localhost:5000";
const $=id=>document.getElementById(id);

// Theme
(()=>document.documentElement.setAttribute("data-theme",localStorage.getItem("fynza_theme")||"dark"))();
const themeBtn = $("theme-toggle");
if(themeBtn){
  themeBtn.innerHTML = document.documentElement.getAttribute("data-theme")==="dark" ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
  themeBtn.addEventListener("click",()=>{
    const n=document.documentElement.getAttribute("data-theme")==="dark"?"light":"dark";
    document.documentElement.setAttribute("data-theme",n);
    localStorage.setItem("fynza_theme",n);
    themeBtn.innerHTML = n === "dark" ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
  });
}

// Animated Cyber Colors (Dynamic RGB)
let currentHue = 160; // Start at cyan (hsl 160)
function animateColors() {
    currentHue = (currentHue + 0.05) % 360; // Slower transition
    document.documentElement.style.setProperty('--accent-color', `hsl(${currentHue}, 100%, 50%)`);
    document.documentElement.style.setProperty('--accent-glow', `hsla(${currentHue}, 100%, 50%, 0.4)`);
    requestAnimationFrame(animateColors);
}
requestAnimationFrame(animateColors);

// Toast
function toast(msg,type="info",ms=4000){const c=$("toast-container");const colors={success:"var(--accent-color)",error:"#ef4444",info:"#7c3aed",warning:"#f59e0b"};const t=document.createElement("div");t.className="toast";t.style.border=`1px solid ${colors[type]||colors.info}`;t.textContent=msg;c.appendChild(t);setTimeout(()=>t.remove(),ms);}

// Helpers
const showAlert=(el,m,t="error")=>{el.textContent=m;el.className=`alert ${t}`;el.hidden=false;};
const clearAlert=el=>{el.hidden=true;el.textContent="";};
const setLoading=(btn,sp,on)=>{btn.disabled=on;sp.hidden=!on;const t=btn.querySelector(".btn-text");if(t)t.style.opacity=on?"0.6":"1";};
const fmt=(n,u="bytes")=>n<1024?`${n} ${u}`:n<1048576?`${(n/1024).toFixed(1)} KB`:`${(n/1048576).toFixed(2)} MB`;
const infoRow=(key,val,cls="")=>`<div class="info-row"><span class="info-key">${key}</span><span class="info-val ${cls}">${val}</span></div>`;

// Tabs
const PANELS=["hide","extract","detect","forensics","performance","logs"];
function switchTab(tab){PANELS.forEach(p=>{$(`${p}-panel`).hidden=p!==tab;[$(`tab-${p}-btn`),$(`nav-${p}-btn`)].forEach(b=>b&&b.classList.toggle("active",p===tab));});if(tab==="logs"){loadStats();renderHistory();}}
PANELS.forEach(p=>{[$(`tab-${p}-btn`),$(`nav-${p}-btn`)].forEach(b=>b&&b.addEventListener("click",()=>switchTab(p)));});
$("goto-detect-btn")?.addEventListener("click",()=>switchTab("detect"));
$("hm-goto-btn")?.addEventListener("click",()=>switchTab("forensics"));

// Dropzone factory — with toolbar + reset support
function mkDrop(dzId,inId,idleId,prevId,toolbarId,fnLblId,onFile,onReset){
  const dz=$(dzId),inp=$(inId),idle=$(idleId),prev=$(prevId),toolbar=$(toolbarId),fnLbl=$(fnLblId);
  dz.addEventListener("click",()=>{if(!dz.classList.contains("has-image"))inp.click();});
  inp.addEventListener("change",()=>{if(inp.files.length)go(inp.files[0]);});
  dz.addEventListener("dragover",e=>{e.preventDefault();dz.classList.add("drag-over");});
  dz.addEventListener("dragleave",()=>dz.classList.remove("drag-over"));
  dz.addEventListener("drop",e=>{e.preventDefault();dz.classList.remove("drag-over");if(e.dataTransfer.files[0])go(e.dataTransfer.files[0]);});
  const origIdleHTML=idle.innerHTML;
  // Reload / change file button
  const reloadBtn=toolbarId.replace("toolbar","reload-btn");
  $(reloadBtn)?.addEventListener("click",()=>{ reset(); if(onReset)onReset(); });
  function reset(){
    inp.value=""; prev.src=""; prev.classList.remove("visible");
    idle.innerHTML=origIdleHTML;
    idle.style.display="block"; dz.classList.remove("has-image","drag-over");
    toolbar.style.display="none"; fnLbl.textContent="";
  }
  function go(f){
    if(f.name.endsWith(".wav")){
      idle.style.display="none"; dz.classList.add("has-image");
      prev.style.display="none";
      idle.style.display="block";
      idle.innerHTML=`<div class="drop-icon"><i class="fa-solid fa-music"></i></div><p class="drop-title">${f.name}</p><p class="drop-sub" style="color:var(--success)">WAV Audio ready</p>`;
    } else if(f.type.startsWith("image/")) {
      const r=new FileReader();r.onload=e=>{prev.src=e.target.result;prev.classList.add("visible");idle.style.display="none";dz.classList.add("has-image");};r.readAsDataURL(f);
    } else {
      // Generic file
      idle.style.display="none"; dz.classList.add("has-image");
      prev.style.display="none";
      idle.style.display="block";
      idle.innerHTML=`<div class="drop-icon"><i class="fa-solid fa-file-code"></i></div><p class="drop-title">${f.name}</p><p class="drop-sub" style="color:var(--success)">File ready</p>`;
    }
    fnLbl.textContent=`${f.name} · ${fmt(f.size)}`;
    toolbar.style.display="flex";
    onFile(f);
  }
}


// State
let hideFile=null,extractFile=null,detectFile=null,secretFile=null,payloadType="text",currentReport=null;

// Dropzones
mkDrop("hide-dropzone","hide-file-input","hide-drop-idle","hide-preview","hide-toolbar","hide-filename",
  f=>{hideFile=f;clearAlert($("hide-alert"));showCarrierInfo(f);},
  ()=>{hideFile=null;$("carrier-info").style.display="none";$("cap-warning").style.display="none";$("hide-result").hidden=true;$("hide-placeholder").hidden=false;$("perf-content").style.display="none";$("perf-placeholder").style.display="block";}
);
mkDrop("extract-dropzone","extract-file-input","extract-drop-idle","extract-preview","extract-toolbar","extract-filename",
  f=>{extractFile=f;clearAlert($("extract-alert"));},
  ()=>{extractFile=null;$("extract-result").hidden=true;$("extract-placeholder").hidden=false;}
);
mkDrop("detect-dropzone","detect-file-input","detect-drop-idle","detect-preview","detect-toolbar","detect-filename",
  f=>{detectFile=f;clearAlert($("detect-alert"));},
  ()=>{detectFile=null;$("detect-result").hidden=true;$("detect-placeholder").hidden=false;}
);

// Carrier info
function showCarrierInfo(f){
  const ext=f.name.split(".").pop().toLowerCase();
  const rows=[infoRow("<i class='fa-solid fa-file-code'></i> Filename",f.name),infoRow("<i class='fa-solid fa-box'></i> File Size",fmt(f.size)),infoRow("<i class='fa-solid fa-film'></i> Format",ext.toUpperCase())];
  $("carrier-info-rows").innerHTML=rows.join("");
  $("carrier-info").style.display="block";
  if($("auto-cap-check").checked)autoCapCheck(f);
}

async function autoCapCheck(f){
  try{
    const fd=new FormData();fd.append("carrier",f);fd.append("algorithm",$("hide-algorithm").value);fd.append("payload_size",payloadType==="text"?new Blob([$("hide-message").value]).size:(secretFile?.size||0));
    const d=(await (await fetch(`${API}/check-capacity`,{method:"POST",body:fd})).json());
    if(!d.success)return;
    $("carrier-info-rows").innerHTML+= infoRow("<i class='fa-solid fa-chart-column'></i> Capacity",fmt(d.capacity_bytes))+infoRow("<i class='fa-solid fa-percent'></i> Used",`${d.used_percent}%`,d.used_percent>80?"warn":d.used_percent>100?"bad":"good");
    const w=$("cap-warning");
    if(d.used_percent>80){w.innerHTML=`<i class="fa-solid fa-triangle-exclamation"></i> ${d.recommendation}`;w.style.display="block";w.className=`cap-warning ${d.used_percent>=100?"":"cap-ok"}`;}
    else{w.style.display="none";}
  }catch(e){}
}

// Payload type
$("type-text-btn").addEventListener("click",()=>{payloadType="text";$("type-text-btn").classList.add("active");$("type-file-btn").classList.remove("active");$("hide-message").style.display="block";$("secret-dropzone").style.display="none";});
$("type-file-btn").addEventListener("click",()=>{payloadType="file";$("type-file-btn").classList.add("active");$("type-text-btn").classList.remove("active");$("hide-message").style.display="none";$("secret-dropzone").style.display="flex";});
$("secret-dropzone").addEventListener("click",()=>$("secret-file-input").click());
$("secret-file-input").addEventListener("change",()=>{if($("secret-file-input").files.length){secretFile=$("secret-file-input").files[0];$("secret-file-name").innerHTML=`<i class="fa-solid fa-paperclip"></i> ${secretFile.name} (${fmt(secretFile.size)})`;}});
$("hide-message").addEventListener("input",()=>{const v=$("hide-message").value;$("char-count").textContent=`${v.length} characters · ${new Blob([v]).size} bytes`;});
$("hide-compression").addEventListener("input",e=>$("comp-lvl-val").textContent=e.target.value);

// Password toggles
function mkPwdToggle(inId,btnId){$(btnId).addEventListener("click",()=>{const i=$(inId);const h=i.type==="password";i.type=h?"text":"password";$(btnId).innerHTML=h?"<i class='fa-solid fa-eye-slash'></i>":"<i class='fa-solid fa-eye'></i>";});}
mkPwdToggle("hide-password","hide-pwd-toggle");
mkPwdToggle("extract-password","extract-pwd-toggle");

// Password strength
$("hide-password").addEventListener("input",()=>{
  const p=$("hide-password").value;let s=0;
  if(p.length>=8)s++;if(p.length>=14)s++;if(/[A-Z]/.test(p)&&/[a-z]/.test(p))s++;if(/[0-9]/.test(p))s++;if(/[^A-Za-z0-9]/.test(p))s++;s=Math.min(s,4);
  $("hide-strength-bar").style.width=(s*25)+"%";
  $("hide-strength-bar").style.background=["transparent","#ef4444","#f59e0b","#3b82f6","var(--accent-color)"][s];
  $("strength-label").textContent=p.length?["","Weak — add more characters","Fair — add symbols & numbers","Good password","Strong password ✓"][s]:"Password strength will appear here";
});

// Explain renderer
function renderExplain(steps,secId,listId){
  const sec=$(secId),lst=$(listId);if(!steps?.length){sec.hidden=true;return;}
  lst.innerHTML=steps.map(s=>`<div class="explain-step"><div class="explain-num">${s.step}</div><div class="explain-text"><strong>${s.title}</strong><span>${s.detail}</span></div></div>`).join("");
  sec.hidden=false;
}

// Stat boxes
function renderStatBoxes(stats){
  const g=$("stat-group");if(!g)return;
  g.innerHTML=[
    ["⏱ Processing",`${stats.processing_time_seconds}s`],
    ["<i class='fa-solid fa-hashtag'></i> Bits Embedded",`${(stats.bits_embedded||0).toLocaleString()}`],
    ["<i class='fa-solid fa-box'></i> Compression",`${stats.compression_ratio||0}% saved`],
    ["<i class='fa-solid fa-chart-column'></i> Carrier Used",`${stats.capacity_used_pct||0}%`],
  ].map(([l,v])=>`<div class="stat-box"><div class="stat-box-val">${v}</div><div class="stat-box-lbl">${l}</div></div>`).join("");
}

// Result metadata rows
function renderMeta(containerId,rows){
  $(containerId).innerHTML=rows.map(([k,v,c])=>infoRow(k,v,c||"")).join("");
}

// HIDE
$("hide-btn").addEventListener("click",async()=>{
  clearAlert($("hide-alert"));
  if(!hideFile)return showAlert($("hide-alert"),"⚠️ Please upload a carrier file.");
  if(payloadType==="text"&&!$("hide-message").value)return showAlert($("hide-alert"),"⚠️ Please type a message.");
  if(payloadType==="file"&&!secretFile)return showAlert($("hide-alert"),"⚠️ Please select a secret file.");
  if(!$("hide-password").value)return showAlert($("hide-alert"),"⚠️ Please enter a password.");

  const fd=new FormData();
  fd.append("image",hideFile);fd.append("password",$("hide-password").value);
  fd.append("algorithm",$("hide-algorithm").value);fd.append("encryption",$("hide-encryption").value);
  fd.append("kdf",$("hide-kdf").value);fd.append("iterations",$("hide-iterations").value);
  fd.append("compression_level",$("hide-compression").value);
  if($("hint-field").value)fd.append("hint",$("hint-field").value);
  if($("question-field").value)fd.append("recovery_question",$("question-field").value);
  if($("answer-field").value)fd.append("recovery_answer",$("answer-field").value);
  if($("explain-mode-hide").checked)fd.append("explain_mode","true");
  let pSize=0;
  if(payloadType==="text"){fd.append("message",$("hide-message").value);pSize=new Blob([$("hide-message").value]).size;}
  else{fd.append("secret_file",secretFile);pSize=secretFile.size;}

  setLoading($("hide-btn"),$("hide-spinner"),true);
  $("hide-result").hidden=true;$("hide-placeholder").hidden=false;
  try{
    const res=await fetch(`${API}/hide`,{method:"POST",body:fd});
    const d=await res.json();
    if(!d.success)throw new Error(d.error||"Server error");
    currentReport=d; // Store full response for PDF reporter
    const st=d.stats||{};
    const sec=d.security||{};
    const cap=d.capacity||1;

    // Gauges
    $("score-val").textContent=`${sec.score||0}/100`;
    $("score-bar").style.width=`${sec.score||0}%`;
    $("score-bar").style.backgroundColor=sec.score>70?"var(--accent-color)":sec.score>40?"var(--warning)":"var(--error)";
    $("risk-val").textContent=sec.risk_level||"—";
    $("risk-val").style.color=sec.risk_level==="Low"?"var(--success)":sec.risk_level==="Medium"?"var(--warning)":"var(--error)";
    const capPct=Math.min(st.capacity_used_pct||0,100);
    $("capacity-pct-val").textContent=`${capPct}%`;
    $("capacity-bar").style.width=`${capPct}%`;
    $("hide-psnr-label").textContent=sec.psnr?`PSNR: ${sec.psnr} dB`:"";

    // Imperceptibility Metrics
    $("metric-mse").textContent=sec.mse!=null?sec.mse.toFixed(5):"—";
    $("metric-mse").className="metric-val "+(sec.mse<0.01?"good":sec.mse<1?"warn":"bad");
    $("metric-psnr").textContent=sec.psnr!=null?`${sec.psnr.toFixed(5)} dB`:"—";
    $("metric-psnr").className="metric-val "+(sec.psnr>50?"good":sec.psnr>35?"warn":"bad");
    $("metric-if").textContent=sec.image_fidelity!=null?sec.image_fidelity.toFixed(5):"—";
    $("metric-if").className="metric-val "+(sec.image_fidelity>0.999?"good":sec.image_fidelity>0.99?"warn":"bad");

    // Robustness Metrics
    $("metric-crc").textContent=sec.correlation!=null?sec.correlation.toFixed(5):"—";
    $("metric-crc").className="metric-val "+(sec.correlation>0.999?"good":sec.correlation>0.99?"warn":"bad");
    $("metric-sim").textContent=sec.similarity!=null?sec.similarity.toFixed(5):"—";
    $("metric-sim").className="metric-val "+(sec.similarity>0.999?"good":sec.similarity>0.99?"warn":"bad");
    $("metric-ber").textContent=sec.ber!=null?`${sec.ber.toFixed(5)}%`:"—";
    $("metric-ber").className="metric-val "+(sec.ber<1?"good":sec.ber<5?"warn":"bad");
    $("metric-ar").textContent=sec.accuracy!=null?`${sec.accuracy.toFixed(5)}%`:"—";
    $("metric-ar").className="metric-val "+(sec.accuracy>99?"good":sec.accuracy>90?"warn":"bad");

    // Update Performance Tab
    $("perf-placeholder").style.display = "none";
    $("perf-content").style.display = "block";
    // (Actual metric IDs remain same, they were moved in index.html)

    renderStatBoxes(st);
    renderMeta("result-meta-rows",[
      ["<i class='fa-solid fa-film'></i> Carrier",d.report?.carrier?.filename||hideFile.name],
      ["<i class='fa-solid fa-box'></i> Original Size",fmt(st.original_size)],
      ["<i class='fa-solid fa-compress'></i> After Compression",fmt(st.compressed_size)+" ("+st.compression_ratio+"% smaller)","good"],
      ["<i class='fa-solid fa-lock'></i> After Encryption",fmt(st.encrypted_size)],
      ["⚙️ Algorithm",$("hide-algorithm").options[$("hide-algorithm").selectedIndex].text],
      ["<i class='fa-solid fa-key'></i> Cipher",$("hide-encryption").options[$("hide-encryption").selectedIndex].text],
      ["<i class='fa-solid fa-brain'></i> KDF",$("hide-kdf").options[$("hide-kdf").selectedIndex].text+" @ "+$("hide-iterations").value+" iterations"],
    ]);

    if(d.media_type==="image"){
      $("image-previews-wrap").style.display="block";
      $("audio-result-wrap").style.display="none";
      $("generic-result-wrap").style.display="none";
      const stegoSrc="data:image/png;base64,"+d.stego_image;
      $("hide-result-img").src=stegoSrc;
      $("hide-download-png").href=stegoSrc;
      $("hide-download-jpg").href="data:image/jpeg;base64,"+d.stego_image;
      // Advanced heatmap viewer
      if(d.heatmap_layers){
        initHeatmapViewer(d.heatmap_layers, d.heatmap_stats, stegoSrc, hideFile);
        $("hide-heatmap-img").style.display="none";
      } else if(d.heatmap_image){
        $("hide-heatmap-img").src="data:image/png;base64,"+d.heatmap_image;
        $("hide-heatmap-img").style.display="block";
      }
    }else if(d.media_type==="audio"){
      $("image-previews-wrap").style.display="none";
      $("generic-result-wrap").style.display="none";
      $("audio-result-wrap").style.display="block";
      const u="data:audio/wav;base64,"+d.stego_audio;
      $("stego-audio-player").src=u;
      $("hide-download-wav").href=u;
    }else{
      // Generic file
      $("image-previews-wrap").style.display="none";
      $("audio-result-wrap").style.display="none";
      $("generic-result-wrap").style.display="block";
      const u="data:application/octet-stream;base64,"+d.generic_data;
      $("hide-download-generic").href=u;
      $("hide-download-generic").download=d.generic_filename || "stego_file.bin";
      $("generic-filename-lbl").textContent=d.generic_filename || "stego_file.bin";
    }

    renderExplain(d.explanations,"explain-section","explain-list");
    $("hide-placeholder").hidden=true;$("hide-result").hidden=false;
    showAlert($("hide-alert"),`✅ Payload hidden in ${st.processing_time_seconds}s — ${fmt(st.original_size)} → ${fmt(st.encrypted_size)}`,"success");
    saveLog("HIDE",$("hide-algorithm").value,pSize/1024,"OK");
    toast("✅ Payload hidden successfully!","success");
  }catch(e){showAlert($("hide-alert"),`❌ ${e.message}`);saveLog("HIDE",$("hide-algorithm").value,pSize/1024,"FAIL");toast(`❌ ${e.message}`,"error");}
  finally{setLoading($("hide-btn"),$("hide-spinner"),false);}
});

// Export
async function exportReport(fmt2){
  if(!currentReport){toast("Run hide first","warning");return;}
  try{
    const res=await fetch(`${API}/export-report?format=${fmt2}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(currentReport)});
    const blob=await res.blob();const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download=`fynza_report.${fmt2}`;a.click();URL.revokeObjectURL(url);
    toast(`✅ ${fmt2.toUpperCase()} report exported!`,"success");
  }catch(e){toast("Export failed","error");}
}
$("export-json-btn").addEventListener("click",()=>exportReport("json"));
$("export-csv-btn").addEventListener("click",()=>exportReport("csv"));
$("export-html-btn").addEventListener("click",()=>exportReport("html"));
$("export-pdf-btn").addEventListener("click",()=>exportReport("pdf"));
$("hm-export-pdf-btn")?.addEventListener("click",()=>exportReport("pdf"));

// EXTRACT
$("extract-btn").addEventListener("click",async()=>{
  clearAlert($("extract-alert"));
  if(!extractFile)return showAlert($("extract-alert"),"⚠️ Please upload a stego file.");
  if(!$("extract-password").value)return showAlert($("extract-alert"),"⚠️ Please enter the password.");
  const fd=new FormData();
  fd.append("image",extractFile);fd.append("password",$("extract-password").value);
  fd.append("algorithm",$("extract-algorithm").value);fd.append("kdf",$("extract-kdf").value);
  fd.append("iterations",$("extract-iterations").value);
  if($("explain-mode-extract").checked)fd.append("explain_mode","true");
  setLoading($("extract-btn"),$("extract-spinner"),true);
  $("extract-result").hidden=true;$("extract-placeholder").hidden=false;
  try{
    const res=await fetch(`${API}/extract`,{method:"POST",body:fd});
    const d=await res.json();
    if(!d.success)throw new Error(d.error||"Extraction failed.");
    if(d.hints&&Object.keys(d.hints).length){$("hint-box").innerHTML=`<i class='fa-solid fa-key'></i> <strong>Hint:</strong> ${d.hints.hint||"—"}<br><i class='fa-solid fa-circle-question'></i> <strong>Q:</strong> ${d.hints.question||"—"}`;$("hint-box").hidden=false;}else{$("hint-box").hidden=true;}
    const s=d.stats||{};
    $("extract-timing").innerHTML=`<i class='fa-solid fa-stopwatch'></i> ${s.processing_time_seconds}s · ${(s.bits_extracted||0).toLocaleString()} bits`;
    renderMeta("extract-meta-rows",[
      ["<i class='fa-solid fa-film'></i> Source File",extractFile.name],
      ["<i class='fa-solid fa-satellite-dish'></i> Media Type",s.media_type||"image"],
      ["<i class='fa-solid fa-hashtag'></i> Bits Extracted",`${(s.bits_extracted||0).toLocaleString()} bits`],
      ["<i class='fa-solid fa-stopwatch'></i> Processing Time",`${s.processing_time_seconds}s`],
      ["<i class='fa-solid fa-file-code'></i> Payload Type",d.type],
    ]);
    const mb=$("extract-message-box"),cpBtn=$("copy-btn"),dlCard=$("file-download-card");
    if(d.type==="text"){
      mb.textContent=d.message;mb.style.display="block";mb.style.whiteSpace="pre-wrap";
      dlCard.style.display="none";
      cpBtn.innerHTML="Copy to Clipboard";
      cpBtn.style.display="inline-flex";
      cpBtn.onclick=async()=>{await navigator.clipboard.writeText(d.message);cpBtn.innerHTML="<i class='fa-solid fa-check'></i> Copied!";setTimeout(()=>{cpBtn.innerHTML="Copy to Clipboard";},2000);};
    }else{
      mb.style.display="none";
      dlCard.style.display="flex";
      $("dl-filename").textContent=d.filename;
      $("dl-filesize").textContent=fmt(d.file_size_bytes);
      const href="data:application/octet-stream;base64,"+d.file_data;
      $("dl-btn").href=href; $("dl-btn").download=d.filename;
      cpBtn.style.display="none";
    }
    $("extract-report-btn").onclick=()=>{const b=new Blob([JSON.stringify(d,null,2)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="extract_report.json";a.click();};
    renderExplain(d.explanations,"extract-explain-section","extract-explain-list");
    $("extract-placeholder").hidden=true;$("extract-result").hidden=false;
    showAlert($("extract-alert"),`✅ Decrypted in ${s.processing_time_seconds}s`,"success");
    saveLog("EXTRACT",$("extract-algorithm").value,extractFile.size/1024,"OK");
    toast("✅ Payload extracted!","success");
  }catch(e){showAlert($("extract-alert"),`❌ ${e.message}`);saveLog("EXTRACT",$("extract-algorithm").value,(extractFile?.size||0)/1024,"FAIL");toast(`❌ ${e.message}`,"error");}
  finally{setLoading($("extract-btn"),$("extract-spinner"),false);}
});

// DETECT
$("detect-btn").addEventListener("click",async()=>{
  clearAlert($("detect-alert"));
  if(!detectFile)return showAlert($("detect-alert"),"⚠️ Please upload an image.");
  setLoading($("detect-btn"),$("detect-spinner"),true);
  try{
    const fd=new FormData();fd.append("image",detectFile);
    const d=(await (await fetch(`${API}/detect`,{method:"POST",body:fd})).json());
    if(!d.success)throw new Error(d.error);
    const det=d.detection;
    const rColor=det.risk_level==="Low"?"var(--success)":det.risk_level==="Medium"?"var(--warning)":"var(--error)";
    const badge=$("detect-badge");badge.innerHTML=`${det.risk_level==="Low"?"<i class='fa-solid fa-check'></i>":"<i class='fa-solid fa-triangle-exclamation'></i>"} ${det.risk_level} Risk`;badge.style.color=rColor;badge.style.borderColor=rColor;
    
    // Legacy stat update
    $("detect-score-val").textContent=`${det.suspicion_score}/100`;$("detect-score-val").style.color=rColor;
    $("detect-score-bar").style.width=`${det.suspicion_score}%`;$("detect-score-bar").style.background=rColor;
    let gridItems = [["Suspicion Score",`${det.suspicion_score}/100`,rColor],["Risk Level",det.risk_level,rColor]];
    gridItems.push(["LSB Ones Ratio",det.lsb_ones_ratio,""]);
    if (det.chi_square_deviation !== undefined) gridItems.push(["Chi-Square Dev.",det.chi_square_deviation,""]);
    $("detect-grid").innerHTML=gridItems.map(([l,v,c])=>`<div class="detect-card"><div class="detect-val" style="color:${c||"var(--text-primary)"}">${v}</div><div class="detect-lbl">${l}</div></div>`).join("");
    
    // AI Output Box Update
    if (det.ai_result) {
        const isStego = det.ai_result.is_stego;
        const stegoIcon = isStego ? "<i class='fa-solid fa-triangle-exclamation'></i> " : "<i class='fa-solid fa-circle-check'></i> ";
        $("ai-stego-val").innerHTML = stegoIcon + (isStego ? "Stego Detected" : "Clean Image");
        $("ai-stego-val").style.color = isStego ? "var(--error)" : "var(--success)";
        
        const methodIcon = isStego ? "<i class='fa-solid fa-microchip'></i> " : "";
        $("ai-method-val").innerHTML = methodIcon + (det.ai_result.method || "None");
        $("ai-method-val").style.color = isStego ? "var(--cyan)" : "var(--text-muted)";
        
        const confPct = (det.ai_result.confidence * 100).toFixed(2);
        $("ai-confidence-val").textContent = `${confPct}%`;
        
        const confBar = $("ai-confidence-bar");
        setTimeout(() => {
            confBar.style.width = `${confPct}%`;
            confBar.style.background = isStego ? "var(--error)" : "var(--success)";
        }, 100);
    } else {
        $("ai-stego-val").textContent = "N/A";
        $("ai-method-val").textContent = "Model not loaded";
        $("ai-confidence-val").textContent = "0%";
        $("ai-confidence-bar").style.width = "0%";
    }

    renderMeta("detect-meta-rows",[
      ["<i class='fa-regular fa-image'></i> Total Pixels",det.total_pixels?.toLocaleString()||"—"],
      ["<i class='fa-solid fa-square' style='color:var(--accent-color)'></i> LSB Ones",det.ones_count?.toLocaleString()||"—"],
      ["<i class='fa-solid fa-square' style='color:#e5e7eb'></i> LSB Zeros",det.zeros_count?.toLocaleString()||"—"],
      ["<i class='fa-solid fa-scale-balanced'></i> Ones Ratio",det.lsb_ones_ratio,(det.lsb_ones_ratio>1.05||det.lsb_ones_ratio<0.95)?"warn":"good"],
      ["<i class='fa-solid fa-list-check'></i> Verdict",det.verdict],
    ]);
    $("detect-placeholder").hidden=true;$("detect-result").hidden=false;
    toast(`Detection: ${det.risk_level} risk`,(det.risk_level==="Low"?"success":"warning"));
  }catch(e){showAlert($("detect-alert"),`❌ ${e.message}`);}
  finally{setLoading($("detect-btn"),$("detect-spinner"),false);}
});

// STATS
async function loadStats(){
  try{
    const d=(await (await fetch(`${API}/statistics`)).json());
    if(!d.success)return;
    const s=d.statistics;
    $("stat-hide").textContent=s.hide_operations;
    $("stat-extract").textContent=s.extract_operations;
    $("stat-bytes").textContent=fmt(s.total_bytes_hidden);
    const body=$("stats-body");body.innerHTML="";
    (s.recent_operations||[]).slice(0,15).forEach(op=>{
      const tr=document.createElement("tr");
      tr.innerHTML=`<td>${op.timestamp}</td><td><strong>${op.type}</strong></td><td>${op.media_type||"—"}</td><td>${op.algorithm||"—"}</td><td>${op.payload_bytes?fmt(op.payload_bytes):"—"}</td>`;
      body.appendChild(tr);
    });
  }catch(e){}
}
$("refresh-stats-btn").addEventListener("click",loadStats);

// DEMO
$("demo-btn").addEventListener("click",async()=>{
  $("demo-btn").disabled=true;toast("Loading demo…","info",2000);
  try{
    const fd=new FormData();fd.append("style","gradient");fd.append("message","medium");
    const d=(await (await fetch(`${API}/demo`,{method:"POST",body:fd})).json());
    if(!d.success)throw new Error(d.error);
    const blob=await fetch("data:image/png;base64,"+d.stego_image).then(r=>r.blob());
    extractFile=new File([blob],"demo_stego.png",{type:"image/png"});
    const reader=new FileReader();
    reader.onload=e=>{$("extract-preview").src=e.target.result;$("extract-preview").classList.add("visible");$("extract-drop-idle").style.display="none";$("extract-dropzone").classList.add("has-image");};
    reader.readAsDataURL(extractFile);
    $("extract-password").value=d.demo_password;
    $("extract-algorithm").value=d.demo_algorithm||"lsb_basic";
    $("extract-kdf").value=d.demo_kdf||"pbkdf2";
    $("extract-iterations").value=d.demo_iterations||"100000";
    switchTab("extract");
    showAlert($("extract-alert"),`✅ Demo loaded! Password: ${d.demo_password} → click Extract`,"success");
    toast(`Demo ready! Password: ${d.demo_password}`,"success",6000);
  }catch(e){toast(`Demo failed: ${e.message}`,"error");}
  finally{$("demo-btn").disabled=false;}
});

// REPLAY
$("replay-btn").addEventListener("click",async()=>{
  try{
    const d=(await (await fetch(`${API}/replay`)).json());
    if(!d.success)return toast("No previous operation","warning");
    const s=d.replay;
    if(s.algorithm)$("hide-algorithm").value=s.algorithm;
    if(s.encryption)$("hide-encryption").value=s.encryption;
    if(s.kdf)$("hide-kdf").value=s.kdf;
    if(s.iterations)$("hide-iterations").value=s.iterations;
    if(s.compression_level){$("hide-compression").value=s.compression_level;$("comp-lvl-val").textContent=s.compression_level;}
    switchTab("hide");toast("✅ Last settings restored!","success");
  }catch(e){toast("Replay failed","error");}
});

// HISTORY
function loadHistory(){return JSON.parse(localStorage.getItem("fynza_history")||"[]");}
function saveLog(op,mode,sizeKb,status){const h=loadHistory();h.unshift({id:Date.now(),date:new Date().toLocaleString(),op,mode,sizeKb:sizeKb.toFixed(1),status});if(h.length>50)h.pop();localStorage.setItem("fynza_history",JSON.stringify(h));renderHistory();}
function renderHistory(){
  const h=loadHistory(),body=$("history-body");body.innerHTML="";
  if(!h.length){body.innerHTML=`<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted)">No logs yet.</td></tr>`;return;}
  h.forEach(log=>{
    const tr=document.createElement("tr");
    tr.innerHTML=`<td>${log.date}</td><td><strong>${log.op}</strong></td><td><span class="info-chip">${log.mode}</span></td><td>${log.sizeKb} KB</td><td style="color:${log.status==="OK"?"var(--success)":"var(--error)"}">${log.status}</td><td><button class="delete-btn" data-id="${log.id}">✕</button></td>`;
    body.appendChild(tr);
  });
  document.querySelectorAll(".delete-btn").forEach(btn=>btn.addEventListener("click",e=>{const id=parseInt(e.target.getAttribute("data-id"));localStorage.setItem("fynza_history",JSON.stringify(loadHistory().filter(x=>x.id!==id)));renderHistory();}));
}
$("clear-history-btn").addEventListener("click",()=>{localStorage.removeItem("fynza_history");renderHistory();toast("Logs cleared","info");});
renderHistory();

// ══════════════════════════════════════════════════════════════════
// ADVANCED HEATMAP VIEWER  (lives in forensics-panel)
// ══════════════════════════════════════════════════════════════════
function initHeatmapViewer(layers, stats, stegoSrc, origFile) {
  const placeholder = $("hm-placeholder");
  const viewer      = $("hm-viewer");
  if(placeholder) placeholder.style.display = "none";
  if(viewer)      viewer.style.display      = "block";

  // Badge on Forensics tab + shortcut button in Hide panel
  const badge    = $("forensics-badge");
  const shortcut = $("hm-shortcut");
  if(badge)    badge.removeAttribute("hidden");
  if(shortcut) shortcut.removeAttribute("hidden");

  // ── State ────────────────────────────────────────────────────
  let currentLayer = "composite";
  let zoomLevel    = 1.0;

  // DOM refs
  const hmImg      = $("hm-active-img");
  const crosshair  = $("hm-crosshair");
  const inspector  = $("hm-inspector");
  const inspBody   = $("hm-inspector-body");
  const cmpWrap    = $("hm-compare");
  const cmpOrigImg = $("hm-cmp-original");
  const cmpStgImg  = $("hm-cmp-stego");
  const cmpDivider = $("hm-cmp-divider");
  const cmpHandle  = $("hm-cmp-handle");

  // Off-screen canvases for pixel inspector
  const cOrig  = document.createElement("canvas");
  const cStego = document.createElement("canvas");
  function loadCanvas(canvas, src) {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => { canvas.width=img.naturalWidth; canvas.height=img.naturalHeight; canvas.getContext("2d").drawImage(img,0,0); };
    img.src = src;
  }
  loadCanvas(cStego, stegoSrc);
  if(cmpStgImg) cmpStgImg.src = stegoSrc;

  // Load original for compare + pixel inspector
  if(origFile) {
    const reader = new FileReader();
    reader.onload = e => {
      const url = e.target.result;
      if(cmpOrigImg) cmpOrigImg.src = url;
      loadCanvas(cOrig, url);
    };
    reader.readAsDataURL(origFile);
  }

  // ── Stats ────────────────────────────────────────────────────
  if(stats) {
    $("hm-modified").textContent  = (stats.modified_pixels||0).toLocaleString();
    $("hm-affected").textContent  = (stats.affected_pct||0) + "%";
    $("hm-pattern").textContent   = stats.pattern_type || "—";
    const {ones=0, zeros=0} = stats.bit_distribution||{};
    const total = ones+zeros;
    $("hm-bit-ratio").textContent = total>0 ? ((ones/total)*100).toFixed(1)+"% ones" : "—";
    const cs=stats.channel_stats||{};
    $("hm-ch-r").textContent = cs.red?.pct   !=null ? cs.red.pct+"%"   : "—";
    $("hm-ch-g").textContent = cs.green?.pct !=null ? cs.green.pct+"%" : "—";
    $("hm-ch-b").textContent = cs.blue?.pct  !=null ? cs.blue.pct+"%"  : "—";
    const rz=stats.risk_zones||{};
    $("hm-risk-safe").textContent  = rz.safe  !=null ? rz.safe+"%"   : "—";
    $("hm-risk-med").textContent   = rz.medium!=null ? rz.medium+"%" : "—";
    $("hm-risk-risky").textContent = rz.risky !=null ? rz.risky+"%"  : "—";
  }

  // ── Layer switching ──────────────────────────────────────────
  function setLayer(name) {
    currentLayer = name;
    if(!layers[name]||!hmImg) return;
    hmImg.src = "data:image/png;base64,"+layers[name];
    document.querySelectorAll(".hm-tab").forEach(b=>b.classList.toggle("active",b.dataset.layer===name));
  }
  document.querySelectorAll(".hm-tab").forEach(btn=>btn.addEventListener("click",()=>setLayer(btn.dataset.layer)));
  setLayer("composite");

  // ── View switching ───────────────────────────────────────────
  function setView(v) {
    const vH=$("hm-view-heatmap"), vC=$("hm-view-compare");
    if(vH) vH.style.display = v==="heatmap"?"flex":"none";
    if(vC) vC.style.display = v==="compare" ?"flex":"none";
    document.querySelectorAll(".hm-view-btn").forEach(b=>b.classList.toggle("active",b.dataset.view===v));
  }
  document.querySelectorAll(".hm-view-btn").forEach(btn=>btn.addEventListener("click",()=>setView(btn.dataset.view)));

  // ── Zoom ─────────────────────────────────────────────────────
  function applyZoom(){
    if(hmImg) hmImg.style.transform=`scale(${zoomLevel})`;
    const lbl=$("hm-zoom-label"); if(lbl) lbl.textContent=Math.round(zoomLevel*100)+"%";
  }
  $("hm-zoom-in") ?.addEventListener("click",()=>{zoomLevel=Math.min(5,   +(zoomLevel+0.25).toFixed(2));applyZoom();});
  $("hm-zoom-out")?.addEventListener("click",()=>{zoomLevel=Math.max(0.25,+(zoomLevel-0.25).toFixed(2));applyZoom();});
  $("hm-zoom-fit")?.addEventListener("click",()=>{zoomLevel=1.0;applyZoom();});

  // ── Pixel Inspector ──────────────────────────────────────────
  if(hmImg){
    hmImg.addEventListener("mousemove",e=>{
      const rect=hmImg.getBoundingClientRect();
      const px=Math.floor((e.clientX-rect.left)*(hmImg.naturalWidth/rect.width));
      const py=Math.floor((e.clientY-rect.top) *(hmImg.naturalHeight/rect.height));
      if(crosshair){crosshair.style.display="block";crosshair.style.left=(e.clientX-rect.left)+"px";crosshair.style.top=(e.clientY-rect.top)+"px";}
      if(cStego.width>0&&inspBody){
        const sPx=cStego.getContext("2d").getImageData(px,py,1,1).data;
        let html=`<div class="hm-px-item"><span class="hm-px-label">Position</span><span class="hm-px-val">${px}, ${py}</span></div>
<div class="hm-px-item"><span class="hm-px-label">Stego RGB</span><span class="hm-px-val">${sPx[0]}, ${sPx[1]}, ${sPx[2]}</span></div>
<div class="hm-px-item"><span class="hm-px-label">Stego LSBs</span><span class="hm-px-val">${sPx[0]&1} ${sPx[1]&1} ${sPx[2]&1}</span></div>`;
        if(cOrig.width>0){
          const oPx=cOrig.getContext("2d").getImageData(px,py,1,1).data;
          const changed=(oPx[0]&1)!==(sPx[0]&1)||(oPx[1]&1)!==(sPx[1]&1)||(oPx[2]&1)!==(sPx[2]&1);
          html+=`<div class="hm-px-item"><span class="hm-px-label">Orig RGB</span><span class="hm-px-val">${oPx[0]}, ${oPx[1]}, ${oPx[2]}</span></div>
<div class="hm-px-item"><span class="hm-px-label">Orig LSBs</span><span class="hm-px-val">${oPx[0]&1} ${oPx[1]&1} ${oPx[2]&1}</span></div>
<div class="hm-px-item"><span class="hm-px-label">Modified</span><span class="hm-px-val ${changed?"hm-px-changed":""}">${changed?"YES ✦":"No"}</span></div>`;
        }
        inspBody.innerHTML=html;
        if(inspector) inspector.removeAttribute("hidden");
      }
    });
    hmImg.addEventListener("mouseleave",()=>{if(crosshair)crosshair.style.display="none";});
  }

  // ── Compare Slider — clip-path ───────────────────────────────
  // cmpOrigImg sits ON TOP clipped; cmpStgImg underneath full width
  let dragging=false;
  function applySplit(pct){
    if(cmpOrigImg) cmpOrigImg.style.clipPath=`inset(0 ${100-pct}% 0 0)`;
    if(cmpDivider) cmpDivider.style.left=pct+"%";
    if(cmpHandle)  cmpHandle.style.left =pct+"%";
  }
  applySplit(50);
  function moveSplit(clientX){
    if(!cmpWrap)return;
    const rect=cmpWrap.getBoundingClientRect();
    applySplit(Math.max(1,Math.min(99,((clientX-rect.left)/rect.width)*100)));
  }
  if(cmpHandle){
    cmpHandle.addEventListener("mousedown", e=>{dragging=true;e.preventDefault();});
    cmpHandle.addEventListener("touchstart",()=>dragging=true,{passive:true});
  }
  document.addEventListener("mousemove", e=>{if(dragging)moveSplit(e.clientX);});
  document.addEventListener("mouseup",   ()=>dragging=false);
  document.addEventListener("touchmove", e=>{if(dragging)moveSplit(e.touches[0].clientX);},{passive:true});
  document.addEventListener("touchend",  ()=>dragging=false);

  // ── Export ───────────────────────────────────────────────────
  $("hm-export-btn")?.addEventListener("click",()=>{
    const a=document.createElement("a");
    a.href=     "data:image/png;base64,"+layers[currentLayer];
    a.download= `fynza_heatmap_${currentLayer}.png`;
    a.click();
    toast("Heatmap exported!","success",2000);
  });
}
