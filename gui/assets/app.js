const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
function metric(val, label) {
    return `
    <div class="metric">
        <strong>${val ?? 0}</strong>
        <span>${esc(label)}</span>
    </div>`;
}
const input=$('#files'), drop=$('#dropzone'), list=$('#file-list'), button=$('#run-button'); let selected=[], timer;

// دالة مساعدة لبناء عناصر الـ Metrics
function metric(val, label) {
    return `
    <div class="metric">
        <strong>${val ?? 0}</strong>
        <span>${esc(label)}</span>
    </div>`;
}

function setFiles(files){selected=[...files].filter(f=>/\.(csv|xlsx)$/i.test(f.name));list.innerHTML=selected.map(f=>`<span>${esc(f.name)} · ${format(f.size)}</span>`).join('');button.disabled=!selected.length}
input.onchange=()=>setFiles(input.files);['dragenter','dragover'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',e=>setFiles(e.dataTransfer.files));

$('#upload-form').onsubmit=async e=>{e.preventDefault();if(!selected.length)return;button.disabled=true;button.querySelector('span').textContent='Starting…';show('process');const body=new FormData();selected.forEach(f=>body.append('files',f));try{const r=await fetch('/api/runs',{method:'POST',body});if(!r.ok)throw new Error((await r.json()).detail||'Upload failed. Check the selected files and try again.');const run=await r.json();poll(run.id)}catch(err){fail(err.message)}};

// زر إعادة التشغيل (New Run & Start Again)
$('#new-run')?.addEventListener('click', () => location.reload());
$('#start-again')?.addEventListener('click', () => location.reload());

function fail(msg) {
    show('error');
    const errEl = $('#error-message');
    if (errEl) errEl.textContent = msg || 'An unexpected error occurred.';
}

function show(name){['upload','process','results','error'].forEach(v=>$(`#${v}-view`).classList.toggle('hidden',v!==name))}

async function poll(id){try{const r=await fetch(`/api/runs/${id}`),run=await r.json();update(run);if(run.status==='complete'){clearTimeout(timer);return loadResults(id)}if(run.status==='failed')return fail(run.message||run.error);timer=setTimeout(()=>poll(id),800)}catch(e){fail(e.message)}}

function update(run){const value=run.progress||0;$('#progress-bar').style.width=`${value}%`;$('.progress-shell').setAttribute('aria-valuenow',value);$('#progress-value').textContent=`${value}%`;$('#progress-label').textContent=title(run.stage||'queued');if(run.file)$('#current-file').textContent=`${run.file}${run.sheet?' · '+run.sheet:''}`;const order=['schema','adaptive','structured','categories','text','validation'],current=order.indexOf(run.stage);$$('#stages>div').forEach((el,i)=>{el.classList.toggle('active',i===current);el.classList.toggle('done',i<current)})}

async function loadResults(id){
    try {
        const r = await fetch(`/api/runs/${id}/results`), data = await r.json(), s = data.summary || {};
        show('results');
        const changes = (s.tables || []).reduce((n,t) => n + (t.changes || 0), 0);
        const issues = (s.tables || []).reduce((n,t) => n + (t.issues || 0), 0);
        const healthScore = s.total_rows ? Math.max(0, 100 - (issues / s.total_rows * 100)).toFixed(1) : '100.0';
        
        const kpiRow = $('#kpi-row');
        if (kpiRow && typeof kpiCard === 'function') {
            kpiRow.innerHTML = 
                kpiCard(s.total_rows || 0, 'Total Records', '#4285F4') + 
                kpiCard(s.processed_tables || 1, 'Tables Cleaned', '#EA4335') + 
                kpiCard(changes, 'Issues Cleaned', '#FBBC05') + 
                kpiCard(healthScore + '%', 'Data Health Score', '#34A853');
        }

        const metricsEl = $('#metrics');
        if (metricsEl) {
            metricsEl.innerHTML = metric(s.processed_tables || 0, 'Tables cleaned') + 
                                  metric(s.total_rows || 0, 'Rows preserved') + 
                                  metric(changes, 'Changes made') + 
                                  metric(issues, 'Review flags');
        }

        const tabs = $('#result-tabs');
        if (tabs && data.tables) {
            tabs.setAttribute('role', 'tablist');
            tabs.innerHTML = data.tables.map((t, i) => `<button role="tab" aria-selected="${i===0}" class="${i?'':'active'}" data-i="${i}">${esc(t.source_file)}${t.sheet ? ' · ' + esc(t.sheet) : ''}</button>`).join('');
            
            tabs.onclick = e => {
                const target = e.target.closest('[data-i]');
                if (!target) return;
                $$('#result-tabs button').forEach(b => {
                    b.classList.remove('active');
                    b.setAttribute('aria-selected', 'false');
                });
                target.classList.add('active');
                target.setAttribute('aria-selected', 'true');
                render(data.tables[Number(target.dataset.i)]);
            };
        }

        if (data.tables && data.tables.length) {
            render(data.tables[0]);
        } else {
            const detail = $('#result-detail');
            if (detail) {
                detail.innerHTML = '<div class="empty-state"><h3>No tables were produced</h3><p>Review the run summary or try another CSV/XLSX file.</p></div>';
            }
        }
    } catch(err) {
        fail(err.message);
    }
}

function renderInsights(insights){
    if(!insights || !insights.length){
        return '<p class="insights-empty">No useful categorical distributions were detected in this table.</p>';
    }

    const tablesMap = {};
    insights.forEach(insight => {
        const tableName = insight.table || insight.sheet || 'Overview Data';
        if (!tablesMap[tableName]) tablesMap[tableName] = [];
        const colName = String(insight.column || '').trim().toLowerCase();
        const exists = tablesMap[tableName].some(i => String(i.column).trim().toLowerCase() === colName);
        if (!exists) tablesMap[tableName].push(insight);
    });

    const tableNames = Object.keys(tablesMap);
    if (tableNames.length === 1) return renderInsightCardsGroup(tablesMap[tableNames[0]]);

    let tabsHeader = `<div class="sheet-tabs-container" style="display:flex; gap:8px; margin-bottom:16px; border-bottom:1px solid #dadce0; padding-bottom:8px; overflow-x:auto;">`;
    let tabsContent = `<div class="sheet-tabs-content">`;

    tableNames.forEach((name, idx) => {
        const isActive = idx === 0 ? 'active' : '';
        const activeStyle = idx === 0 ? 'background:#1a73e8; color:#fff; font-weight:600;' : 'background:#f1f3f4; color:#3c4043;';
        tabsHeader += `<button class="sheet-tab-btn ${isActive}" onclick="switchSheetTab(this, 'sheet-tab-${idx}')" style="padding: 6px 16px; border-radius: 16px; border: none; cursor: pointer; font-size: 13px; transition: all 0.2s; ${activeStyle}">${esc(name)} (${tablesMap[name].length})</button>`;
        tabsContent += `<div id="sheet-tab-${idx}" class="sheet-tab-pane" style="display: ${idx === 0 ? 'grid' : 'none'}; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px;">${renderInsightCardsGroup(tablesMap[name])}</div>`;
    });

    return tabsHeader + `</div>` + tabsContent + `</div>`;
}

function renderInsightCardsGroup(cardsList) {
    return cardsList.map(insight => {
        const col = String(insight.column || '').toLowerCase();
        if(col.includes('depart') || col.includes('dept') || col.includes('قسم') || col.includes('track') || col.includes('skill') || col.includes('major') || col.includes('college') || col.includes('university') || col.includes('where') || col.includes('which')) {
            return renderBarInsight(insight, true, false);
        }
        if(col.includes('level') || col.includes('academic') || col.includes('grade') || col.includes('year') || col.includes('مستوى') || col.includes('سنة')) {
            return renderBarInsight(insight, false, true);
        }
        if(col.includes('role') || col.includes('دور') || col.includes('type') || col.includes('participat') || (insight.categories && insight.categories.length <= 3)) {
            return renderDonutInsight(insight);
        }
        return renderBarInsight(insight, true, false);
    }).join('');
}

window.switchSheetTab = function(btnElement, tabId) {
    document.querySelectorAll('.sheet-tab-pane').forEach(pane => pane.style.display = 'none');
    document.querySelectorAll('.sheet-tab-btn').forEach(btn => {
        btn.style.background = '#f1f3f4';
        btn.style.color = '#3c4043';
        btn.style.fontWeight = 'normal';
    });
    document.getElementById(tabId).style.display = 'grid';
    btnElement.style.background = '#1a73e8';
    btnElement.style.color = '#fff';
    btnElement.style.fontWeight = '600';
};

function renderBarInsight(insight, horizontal, sortNumeric){
    let categories = (insight.categories || []).slice();
    if(sortNumeric){
        categories.sort((a,b)=>{
            const na = parseInt(String(a.value).match(/\d+/)) || 0;
            const nb = parseInt(String(b.value).match(/\d+/)) || 0;
            return na - nb;
        });
    } else {
        categories.sort((a,b) => (Number(b.count) || 0) - (Number(a.count) || 0));
    }
    
    const max = Math.max(...categories.map(c => Number(c.count) || 0), 1);
    const bars = categories.map((c, i) => {
        const pct = ((Number(c.count) || 0) / max * 100).toFixed(1);
        const color = getInsightColor(i);
        const countFormatted = Intl.NumberFormat().format(c.count);

        if (horizontal) {
            return `<div class="bar-row h"><span class="bar-label" title="${esc(c.value)}">${esc(c.value)}</span><div class="bar-track"><div class="bar-fill" style="width:${pct}%; height:100%; background:${color}; display:block;"></div></div><strong class="bar-value">${countFormatted}</strong></div>`;
        } else {
            return `<div class="bar-row v"><strong class="bar-value">${countFormatted}</strong><div class="bar-track"><div class="bar-fill" style="height:${pct}%;background:${color}"></div></div><span class="bar-label" title="${esc(c.value)}">${esc(c.value)}</span></div>`;
        }
    }).join('');

    return `<div class="insight-card"><div class="insight-card-head"><h5>${esc(title(insight.column))}</h5><span>${Intl.NumberFormat().format(insight.total)} values</span></div><div class="bar-chart ${horizontal ? 'bar-chart-h' : 'bar-chart-v'}">${bars}</div></div>`;
}

function renderDonutInsight(insight){
    const categories=insight.categories||[];
    let currentAngle=0;
    const slices=categories.map((category,index)=>{const startAngle=currentAngle;currentAngle+=Number(category.percentage)||0;return `${getInsightColor(index)} ${startAngle}% ${currentAngle}%`}).join(",");
    const legend=categories.map((category,index)=>`<div class="pie-legend-row"><span class="pie-legend-color" style="background:${getInsightColor(index)}"></span><span class="pie-legend-name" title="${esc(category.value)}">${esc(category.value)}</span><strong>${Intl.NumberFormat().format(category.count)}</strong><small>${category.percentage}%</small></div>`).join("");
    return `<div class="insight-card"><div class="insight-card-head"><h5>${esc(title(insight.column))}</h5><span>${Intl.NumberFormat().format(insight.total)} values</span></div><div class="pie-content"><div class="donut-chart" style="background:conic-gradient(${slices})"><div class="donut-center"><strong>${Intl.NumberFormat().format(insight.total)}</strong><span>Total</span></div></div><div class="pie-legend">${legend}</div></div></div>`;
}

function getInsightColor(index){
    const googleColors = ["#4285F4", "#EA4335", "#FBBC05", "#34A853", "#174EA6", "#A50E0E", "#E37400", "#0D652D", "#8AB4F8", "#F28B82"];
    return googleColors[index % googleColors.length];
}

function render(t){
    const cols = t.columns_preview || [];
    const rows = t.rows_preview || [];
    const table = `<table><thead><tr>${cols.map(c=>`<th scope="col">${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td title="${esc(r[c])}">${esc(r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    const changes = t.changes_preview || t.modifications || [];
    let changesHtml = '';

    if (changes.length > 0) {
        const changeRows = changes.map(c => `
            <tr>
                <td><strong>${esc(c.column || c.field || 'Field')}</strong></td>
                <td><span class="val-before">${esc(c.before || c.original || 'empty')}</span></td>
                <td><span class="val-after">${esc(c.after || c.cleaned || 'empty')}</span></td>
                <td><small class="change-reason">${esc(c.reason || c.rule || 'Cleaned')}</small></td>
            </tr>
        `).join('');

        changesHtml = `<div class="changes-panel" style="margin-top:20px; background:#f8f9fa; border:1px solid #dadce0; border-radius:8px; padding:16px;"><h4 style="margin-top:0; color:#202124; font-size:15px; display:flex; align-items:center; gap:8px;"><span>✨</span> Applied Transformations (Before & After)</h4><div class="table-wrap" style="max-height:250px; overflow-y:auto;"><table class="changes-table" style="width:100%; font-size:13px;"><thead><tr style="background:#e8eaed;"><th>Column</th><th>Original (Before)</th><th>Cleaned (After)</th><th>Action / Reason</th></tr></thead><tbody>${changeRows}</tbody></table></div></div>`;
    } else {
        changesHtml = `<div class="changes-panel" style="margin-top:20px; background:#f8f9fa; border:1px solid #dadce0; border-radius:8px; padding:12px; color:#5f6368; font-size:13px;">ℹ️ No direct cell modifications were required for this table.</div>`;
    }

    const insights = renderInsights(t.data_insights);
    const decisions = (t.adaptive_decisions || []).map(d => `<li><span class="decision ${esc(d.status)}">${esc(title(d.status))}</span><strong>${esc(title(d.operation))}</strong><small>${esc(d.reason)}</small></li>`).join('') || '<li class="empty">No unfamiliar mechanical patterns were proposed.</li>';

    $('#result-detail').innerHTML = `
    <article class="result-card">
        <div class="result-toolbar">
            <h3>${esc(t.source_file)} · ${Intl.NumberFormat().format(t.rows || 0)} rows</h3>
            <div class="downloads">
                <a class="secondary-link" href="${t.report_download}">Audit JSON</a>
                <a class="download" href="${t.download}">Download CSV ↓</a>
            </div>
        </div>
        <div class="table-wrap">${table}</div>
        ${changesHtml}
        <div class="adaptive-panel">
            <h4>Adaptive Planner</h4>
            <ul>${decisions}</ul>
        </div>
        <div class="insights">
            <div class="insights-heading">
                <div>
                    <h4>Data Insights</h4>
                    <p>Distributions discovered automatically from the cleaned data.</p>
                </div>
            </div>
            <div class="insights-grid">${insights}</div>
        </div>
    </article>`;
}

function title(s){return String(s).replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())}
function format(n){return n>1e6?`${(n/1e6).toFixed(1)} MB`:`${Math.ceil(n/1e3)} KB`}
function value(v){return v==null?'empty':String(v)}
function esc(v){return value(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}

function kpiCard(value, title, color) {
    return `
    <div class="kpi-card" style="border-top: 4px solid ${color};">
        <strong>${value}</strong>
        <span>${esc(title)}</span>
    </div>`;
}