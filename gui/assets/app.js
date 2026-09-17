const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const input=$('#files'), drop=$('#dropzone'), list=$('#file-list'), button=$('#run-button'); let selected=[], timer;
function setFiles(files){selected=[...files].filter(f=>/\.(csv|xlsx)$/i.test(f.name));list.innerHTML=selected.map(f=>`<span>${esc(f.name)} · ${format(f.size)}</span>`).join('');button.disabled=!selected.length}
input.onchange=()=>setFiles(input.files);['dragenter','dragover'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',e=>setFiles(e.dataTransfer.files));
$('#upload-form').onsubmit=async e=>{e.preventDefault();if(!selected.length)return;button.disabled=true;button.querySelector('span').textContent='Starting…';show('process');const body=new FormData();selected.forEach(f=>body.append('files',f));try{const r=await fetch('/api/runs',{method:'POST',body});if(!r.ok)throw new Error((await r.json()).detail||'Upload failed. Check the selected files and try again.');const run=await r.json();poll(run.id)}catch(err){fail(err.message)}};
function show(name){['upload','process','results','error'].forEach(v=>$(`#${v}-view`).classList.toggle('hidden',v!==name))}
async function poll(id){try{const r=await fetch(`/api/runs/${id}`),run=await r.json();update(run);if(run.status==='complete'){clearTimeout(timer);return loadResults(id)}if(run.status==='failed')return fail(run.message||run.error);timer=setTimeout(()=>poll(id),800)}catch(e){fail(e.message)}}
function update(run){const value=run.progress||0;$('#progress-bar').style.width=`${value}%`;$('.progress-shell').setAttribute('aria-valuenow',value);$('#progress-value').textContent=`${value}%`;$('#progress-label').textContent=title(run.stage||'queued');if(run.file)$('#current-file').textContent=`${run.file}${run.sheet?' · '+run.sheet:''}`;const order=['schema','adaptive','structured','categories','text','validation'],current=order.indexOf(run.stage);$$('#stages>div').forEach((el,i)=>{el.classList.toggle('active',i===current);el.classList.toggle('done',i<current)})}
async function loadResults(id){const r=await fetch(`/api/runs/${id}/results`),data=await r.json(),s=data.summary;show('results');const changes=s.tables.reduce((n,t)=>n+(t.changes||0),0),issues=s.tables.reduce((n,t)=>n+(t.issues||0),0);$('#metrics').innerHTML=metric(s.processed_tables,'Tables cleaned')+metric(s.total_rows,'Rows preserved')+metric(changes,'Changes made')+metric(issues,'Review flags');const tabs=$('#result-tabs');tabs.setAttribute('role','tablist');tabs.innerHTML=data.tables.map((t,i)=>`<button role="tab" aria-selected="${i===0}" class="${i?'':'active'}" data-i="${i}">${esc(t.source_file)}${t.sheet?' · '+esc(t.sheet):''}</button>`).join('');tabs.onclick=e=>{const target=e.target.closest('[data-i]');if(!target)return;$$('#result-tabs button').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-selected','false')});target.classList.add('active');target.setAttribute('aria-selected','true');render(data.tables[Number(target.dataset.i)])};if(data.tables.length)render(data.tables[0]);else $('#result-detail').innerHTML='<div class="empty-state"><h3>No tables were produced</h3><p>Review the run summary or try another CSV/XLSX file.</p></div>'}
function renderInsights(insights){
    if(!insights || !insights.length){
        return '<p class="insights-empty">No useful categorical distributions were detected in this table.</p>';
    }

    return insights.map(insight=>{
        const categories=insight.categories||[];

        let currentAngle=0;

        const slices=categories.map((category,index)=>{
            const startAngle=currentAngle;
            currentAngle+=Number(category.percentage)||0;

            return `${getInsightColor(index)} ${startAngle}% ${currentAngle}%`;
        }).join(",");

        const legend=categories.map((category,index)=>`
            <div class="pie-legend-row">
                <span class="pie-legend-color" style="background:${getInsightColor(index)}"></span>

                <span class="pie-legend-name" title="${esc(category.value)}">
                    ${esc(category.value)}
                </span>

                <strong>${Intl.NumberFormat().format(category.count)}</strong>

                <small>${category.percentage}%</small>
            </div>
        `).join("");

        return `
            <div class="insight-card">
                <div class="insight-card-head">
                    <h5>${esc(title(insight.column))}</h5>
                    <span>${Intl.NumberFormat().format(insight.total)} values</span>
                </div>

                <div class="pie-content">

                    <div
                        class="donut-chart"
                        style="background:conic-gradient(${slices})"
                    >
                        <div class="donut-center">
                            <strong>${Intl.NumberFormat().format(insight.total)}</strong>
                            <span>Total</span>
                        </div>
                    </div>

                    <div class="pie-legend">
                        ${legend}
                    </div>

                </div>
            </div>
        `;
    }).join('');
}

function getInsightColor(index){
    const colors=[
        "#4285F4",
        "#EA4335",
        "#FBBC04",
        "#34A853",
        "#A142F4",
        "#24C1E0",
        "#F06292",
        "#5F6368",
        "#FF7043",
        "#7CB342",
        "#AB47BC",
        "#26A69A"
    ];

    return colors[index % colors.length];
}

function render(t){const cols=t.columns_preview,rows=t.rows_preview;const table=`<table><thead><tr>${cols.map(c=>`<th scope="col">${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td title="${esc(r[c])}">${esc(r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;const insights=renderInsights(t.data_insights);const decisions=(t.adaptive_decisions||[]).map(d=>`<li><span class="decision ${esc(d.status)}">${esc(title(d.status))}</span><strong>${esc(title(d.operation))}</strong><small>${esc(d.reason)}</small></li>`).join('')||'<li class="empty">No unfamiliar mechanical patterns were proposed.</li>';$('#result-detail').innerHTML=`<article class="result-card"><div class="result-toolbar"><h3>${esc(t.source_file)} · ${Intl.NumberFormat().format(t.rows)} rows</h3><div class="downloads"><a class="secondary-link" href="${t.report_download}">Audit JSON</a><a class="download" href="${t.download}">Download CSV ↓</a></div></div><div class="table-wrap">${table}</div><div class="adaptive-panel"><h4>Adaptive Planner</h4><ul>${decisions}</ul></div><div class="insights">
    <div class="insights-heading">
        <div>
            <h4>Data Insights</h4>
            <p>Distributions discovered automatically from the cleaned data.</p>
        </div>
    </div>
    <div class="insights-grid">${insights}</div>
</div></article>`}
$('#new-run').onclick=()=>location.reload();$('#start-again').onclick=()=>location.reload();function fail(msg){clearTimeout(timer);show('error');$('#error-message').textContent=msg;$('#start-again').focus()}function metric(n,label){return `<div class="metric"><strong>${Intl.NumberFormat().format(Number(n||0))}</strong><span>${label}</span></div>`}function title(s){return String(s).replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())}function format(n){return n>1e6?`${(n/1e6).toFixed(1)} MB`:`${Math.ceil(n/1e3)} KB`}function value(v){return v==null?'empty':String(v)}function esc(v){return value(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
