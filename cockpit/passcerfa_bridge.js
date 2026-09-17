#!/usr/bin/env node
// passcerfa_bridge — pont Turbo OS -> services passcerfa (réutilise l'existant).
// fichier -> (OCR tesseract si image/PDF) -> texte -> détection CERFA -> extraction champs -> flag facture.
// Usage: node passcerfa_bridge.js <chemin_fichier>   → JSON sur stdout.
const path = require('path');
const fs = require('fs');
const S = '/home/turbo/MOISSON/github-repos/passcerfa-app/services';
const { detectForm } = require(path.join(S, 'paper-detector.js'));
let extractText = null, extractFields = null;
try { ({ extractText } = require(path.join(S, 'ocr-engine.js'))); } catch (e) {}
try { ({ extractFields } = require(path.join(S, 'field-extractor.js'))); } catch (e) {}

(async () => {
  const file = process.argv[2];
  if (!file || !fs.existsSync(file)) { console.log(JSON.stringify({ ok: false, error: 'fichier introuvable' })); return; }
  const ext = path.extname(file).toLowerCase();
  const isDoc = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp', '.pdf'].includes(ext);
  let text = '';
  try {
    if (isDoc && extractText) { text = (await extractText(file, { lang: 'fra' })) || ''; }
    else { text = fs.readFileSync(file, 'utf8'); }
  } catch (e) { console.log(JSON.stringify({ ok: false, error: 'lecture: ' + e.message })); return; }
  const det = detectForm(text || '');
  const best = det && det.best ? det.best : null;
  let champs = null;
  try { if (extractFields && best) champs = extractFields(text, best.cerfa); } catch (e) {}
  const facture = /factur|invoice|montant|\btva\b|total\s*ttc|siren|siret/i.test(text || '');
  console.log(JSON.stringify({
    ok: true,
    source: isDoc ? (extractText ? 'ocr' : 'doc') : 'texte',
    detected: best ? { cerfa: best.cerfa, label: best.label, demarche: best.demarche, confidence: det.confidence } : null,
    facture,
    facturx_disponible: facture,
    champs: champs || null,
    texte_extrait: (text || '').slice(0, 1500),
  }));
})();
