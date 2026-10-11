const $ = id => document.getElementById(id);
const state = {mode:'Combined context', views:{}, running:false, selected:false, hasResult:false, reviewerReady:false};
const toast = message => { $('toast').textContent=message; $('toast').classList.add('show'); setTimeout(()=>$('toast').classList.remove('show'),3500); };
const setRunning = running => { state.running=running; $('startBtn').classList.toggle('hidden',running); $('cancelBtn').classList.toggle('hidden',!running); $('videoPicker').disabled=running; };
const showTranscript = text => { $('emptyState').classList.add('hidden'); $('transcript').classList.remove('hidden'); $('transcript').textContent=text || 'No content was found for this view.'; };
const updateExportButtons = () => { const ready=state.hasResult && (state.mode!=='Reviewer' || state.reviewerReady); $('wordBtn').disabled=!ready; $('pdfBtn').disabled=!ready; };
const selectMode = mode => { state.mode=mode; document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode)); $('outputTitle').textContent=mode==='Reviewer'?'Study Reviewer':'Transcript'; if(state.views[mode]!==undefined)showTranscript(state.views[mode]); else if(mode==='Reviewer')showTranscript(state.hasResult?'Click “Create Reviewer” to make a short study guide.':'Finish a transcription before creating a reviewer.'); else if(state.running&&mode==='Screen context')showTranscript('Screen context will appear after the audio stage reaches 55%.'); updateExportButtons(); };
const setProgress = (value,status) => {
  const pct=Math.max(0,Math.min(100,Math.round(value*100))); $('progressBar').style.width=pct+'%'; $('percent').textContent=pct+'%'; $('status').textContent=status;
  const labels=document.querySelectorAll('.stages span'); labels.forEach(x=>x.classList.remove('active')); labels[pct<55?0:pct<95?1:pct<100?2:3].classList.add('active');
  $('stage').textContent=pct<55?'Transcribing audio':pct<95?'Reading screen context':pct<100?'Combining results':'Transcript ready';
};

window.addEventListener('pywebviewready',()=>{
  $('videoPicker').onclick=async()=>{ const r=await pywebview.api.select_video(); if(!r.ok)return; state.selected=true; $('videoName').textContent=r.name; $('videoMeta').textContent=(r.size/1048576).toFixed(1)+' MB · Ready to process'; $('startBtn').disabled=false; toast('Video selected'); };
  $('startBtn').onclick=async()=>{ state.views={}; state.hasResult=false; state.reviewerReady=false; $('reviewerBtn').disabled=true; selectMode('Combined context'); showTranscript('Preparing the speech model…'); setProgress(0,'Starting local processing…'); setRunning(true); updateExportButtons(); $('statusPill').textContent='Processing'; $('statusPill').className='status-pill running'; const r=await pywebview.api.start_transcription({processing_mode:$('processingMode').value,model:$('model').value,language:$('language').value,interval:$('interval').value,use_gpu:$('useGpu').checked,use_ollama:$('useOllama').checked,ollama_model:$('ollamaModel').value}); if(!r.ok){setRunning(false);toast(r.error);} };
  $('cancelBtn').onclick=async()=>{ await pywebview.api.cancel(); $('status').textContent='Cancelling after the current operation…'; };
  $('wordBtn').onclick=()=>exportFile('word'); $('pdfBtn').onclick=()=>exportFile('pdf');
  $('reviewerBtn').onclick=async()=>{ selectMode('Reviewer'); showTranscript('Creating a simple reviewer with local Ollama…'); setRunning(true); $('reviewerBtn').disabled=true; $('statusPill').textContent='Creating reviewer'; $('statusPill').className='status-pill running'; const r=await pywebview.api.create_reviewer(); if(!r.ok){setRunning(false);$('reviewerBtn').disabled=false;selectMode('Reviewer');toast(r.error);} };
});

async function exportFile(format){ const r=await pywebview.api.export(format,state.mode); if(r.ok)toast('Saved to '+r.path); else if(!r.cancelled)toast(r.error); }
$('useOllama').onchange=()=> $('ollamaWrap').classList.toggle('hidden',!$('useOllama').checked);
document.querySelectorAll('.tabs button').forEach(button=>button.onclick=()=>selectMode(button.dataset.mode));

window.app={receiveEvent(event){
  if(event.type==='progress'){setProgress(event.value,event.status);return;}
  if(event.type==='segment'){if(state.mode==='Combined context'||state.mode==='Audio only'){const old=$('transcript').textContent==='Preparing the speech model…'?'':$('transcript').textContent;$('transcript').textContent=old+`[${event.start} - ${event.end}] ${event.text}\n\n`;$('transcript').scrollTop=$('transcript').scrollHeight;}return;}
  if(event.type==='complete'){state.views=event.views;state.hasResult=true;setRunning(false);setProgress(1,'Complete · '+event.audio_count+' speech segments · '+event.screen_count+' screen captures');selectMode(state.mode);$('reviewerBtn').disabled=false;$('statusPill').textContent='Complete';$('statusPill').className='status-pill complete';toast('Transcription complete');return;}
  if(event.type==='reviewer_progress'){$('stage').textContent='Creating reviewer';$('status').textContent=event.uses_ollama?'Ollama is organizing the transcript locally…':'Creating a simple reviewer from the transcript…';return;}
  if(event.type==='reviewer_fallback'){$('status').textContent=event.message;toast(event.message);return;}
  if(event.type==='reviewer_complete'){state.views['Reviewer']=event.content;state.reviewerReady=true;setRunning(false);$('reviewerBtn').disabled=false;selectMode('Reviewer');$('stage').textContent='Reviewer ready';$('status').textContent=event.sampled?'Quick reviewer created from selected parts of the long transcript.':(event.uses_ollama?'Local AI reviewer created.':'Simple demonstration reviewer created.');$('statusPill').textContent='Reviewer ready';$('statusPill').className='status-pill complete';toast('Reviewer complete');return;}
  if(event.type==='reviewer_cancelled'){setRunning(false);$('reviewerBtn').disabled=false;updateExportButtons();$('statusPill').textContent='Cancelled';$('statusPill').className='status-pill';toast(event.message);return;}
  if(event.type==='reviewer_error'){setRunning(false);$('reviewerBtn').disabled=false;updateExportButtons();$('statusPill').textContent='Transcript ready';$('statusPill').className='status-pill complete';toast('Reviewer failed: '+event.message);return;}
  if(event.type==='cancelled'){setRunning(false);$('statusPill').textContent='Cancelled';$('statusPill').className='status-pill';toast(event.message);return;}
  if(event.type==='error'){setRunning(false);$('statusPill').textContent='Error';$('statusPill').className='status-pill error';$('stage').textContent='Processing failed';$('status').textContent=event.message;toast(event.message);}
}};
