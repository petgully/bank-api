// ====== CONFIG ======
const CLASSIFIER_URL = 'https://bank-api.52-44-174-19.sslip.io/classify';
const SYNC_URL       = 'https://bank-api.52-44-174-19.sslip.io/sync';
const LEARN_RULES_URL = 'https://bank-api.52-44-174-19.sslip.io/learn-rules';
const RULE_STATS_URL = 'https://bank-api.52-44-174-19.sslip.io/rule-stats';
const CLEAR_CACHE_URL = 'https://bank-api.52-44-174-19.sslip.io/clear-cache';
const API_KEY        = 'supersecret686';   // same value you used in docker run


const SHEET_RAW      = 'Raw';
const SHEET_REVIEW   = 'Needs_Review';
const SHEET_PUB      = 'Published';
const SHEET_MAINCAT  = 'Main_Categories';


// ====== BANK RAW → NORMALIZED CONFIG ======
const SHEET_BANKRAW = 'BankRaw_Statement';     // source pasted data
const NORMALIZE_OUTPUT_PREFIX = 'Normalized';   // new sheet name prefix
const NORMALIZE_ACCOUNT = 'HDFC1681';           // constant Account value
const NORMALIZE_CURRENCY = 'INR';               // constant Currency value

// Header synonyms so we can match varied bank exports
const BANK_HEADER_SYNONYMS = {
  date:      ['Date', 'Txn Date', 'Value Date', 'Transaction Date'],
  desc:      ['Narration', 'Description', 'Particulars', 'Details', 'Transaction Remarks'],
  withdraw:  ['Withdrawal Amount', 'Withdrawal', 'Debit', 'Dr', 'Debit Amount', 'Debits', 'WD'],
  deposit:   ['Deposit Amount', 'Deposit', 'Credit', 'Cr', 'Credit Amount', 'CR'],
  balance:   ['Closing Balance', 'Balance', 'Running Balance', 'Available Balance', 'Avail Balance'],
  amount:    ['Amount', 'Transaction Amount', 'Amt'],     // optional fallback if only one Amount column
  side:      ['Type', 'Dr/Cr', 'Debit/Credit']            // optional fallback when Amount + side indicator
};


// Expected Raw columns (A:F): Date, Description, Amount, Balance, Account, Currency
const RAW_HEADER = ['Date','Description','Amount','Balance','Account','Currency'];

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('Bank Ops')
    .addItem('0) Convert BankRaw_Statement → New normalized sheet', 'menuNormalizeBankRaw')
    .addSeparator()
    .addItem('1) Normalize & Classify (selected rows or all)', 'menuClassify')
    .addItem('2) Approve & Publish to MySQL', 'menuApproveAndPublish')
    .addSeparator()
    .addItem('3) Learn New Rules from Database', 'menuLearnRules')
    .addItem('4) Show Rule Statistics', 'menuRuleStats')
    .addItem('5) Clear Rules Cache (Force Reload)', 'menuClearCache')
    .addToUi();
}

function menuClassify() {
  const ss = SpreadsheetApp.getActive();
  if (!ss) {
    SpreadsheetApp.getUi().alert('No active spreadsheet found. Please open a spreadsheet and try again.');
    return;
  }
  
  const raw = ss.getSheetByName(SHEET_RAW);
  if (!raw) {
    SpreadsheetApp.getUi().alert(`Sheet "${SHEET_RAW}" not found. Please make sure the sheet exists.`);
    return;
  }
  
  // Get active range safely
  let range = null;
  try {
    range = raw.getActiveRange();
  } catch (e) {
    console.log('No active range, using full data range');
  }
  
  const values = (range && range.getNumRows() > 1) ? range.getValues() : raw.getDataRange().getValues();

  // --- header check ---
  const header = values[0];
  if (JSON.stringify(header) !== JSON.stringify(RAW_HEADER)) {
    SpreadsheetApp.getUi().alert('Raw header mismatch.\nExpected: ' + RAW_HEADER.join(', '));
    return;
  }

  // --- build payload from non-empty rows ---
  const data = values.slice(1).filter(r => r[0] && r[1]); // Date & Description present
  const payload = data.map((r, i) => ({
    row_index: i + 2, // 1-based + header
    date: new Date(r[0]).toISOString().slice(0,10),
    description: String(r[1]).trim(),
    amount: Number(r[2]),
    balance: (r[3] !== '' ? Number(r[3]) : null),
    account: String(r[4] || ''),
    currency: String(r[5] || 'INR')
  }));

  if (!payload.length) {
    SpreadsheetApp.getUi().alert('No rows to classify.');
    return;
  }

  // --- single fetch WITH headers ---
  const res = UrlFetchApp.fetch(CLASSIFIER_URL, {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-API-Key': API_KEY },
    payload: JSON.stringify({ rows: payload }),
    muteHttpExceptions: true
  });

  if (res.getResponseCode() !== 200) {
    SpreadsheetApp.getUi().alert('Classifier error: ' + res.getContentText());
    return;
  }

  const out = JSON.parse(res.getContentText());
  writeReview(out);
  SpreadsheetApp.getUi().alert(`Classified: ${out.length} rows. Check "${SHEET_REVIEW}".`);
}


function writeReview(preds) {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(SHEET_REVIEW);
  if (!sh) sh = ss.insertSheet(SHEET_REVIEW);

  sh.clear();
  const header = [
    'Approved', 'Date','Description','Amount','Account','Currency',
    'Vendor','RuleHit','MainCategorySuggested','SubCategorySuggested','Confidence',
    'FinalMainCategory','FinalSubCategory','Notes','RawRow'
  ];
  sh.getRange(1,1,1,header.length).setValues([header]);

  const rows = preds.map(p => ([
    false, p.date, p.description, p.amount, p.account, p.currency,
    p.vendor, p.rule_hit || '', p.main_category_suggested, p.sub_category_suggested, p.confidence,
    p.main_category_suggested, p.sub_category_suggested, '', p.row_index
  ]));
  if (rows.length) sh.getRange(2,1,rows.length,rows[0].length).setValues(rows);

  // Data validation for FinalMainCategory from Main_Categories tab
  const catSheet = ss.getSheetByName(SHEET_MAINCAT);
  if (catSheet) {
    const last = catSheet.getLastRow();
    const rule = SpreadsheetApp.newDataValidation()
      .requireValueInRange(catSheet.getRange(1,1,last,1), true).build();
    sh.getRange(2,12,Math.max(1,rows.length),1).setDataValidation(rule);
  }
}

function menuApproveAndPublish() {
  const ss = SpreadsheetApp.getActive();
  if (!ss) {
    SpreadsheetApp.getUi().alert('No active spreadsheet found. Please open a spreadsheet and try again.');
    return;
  }
  
  const sh = ss.getSheetByName(SHEET_REVIEW);
  if (!sh) { 
    SpreadsheetApp.getUi().alert('No review sheet found. Please run "Normalize & Classify" first.'); 
    return; 
  }

  const vals = sh.getDataRange().getValues();
  const header = vals[0];
  const idx = (name) => header.indexOf(name);

  const approved = vals.slice(1).filter(r => r[idx('Approved')] === true).map(r => ({
    date: new Date(r[idx('Date')]).toISOString().slice(0,10),
    description: r[idx('Description')],
    amount: Number(r[idx('Amount')]),
    account: r[idx('Account')],
    currency: r[idx('Currency')],
    vendor: r[idx('Vendor')],
    main_category: r[idx('FinalMainCategory')],
    sub_category: r[idx('FinalSubCategory')],
    confidence: Number(r[idx('Confidence')]),
    rule_hit: r[idx('RuleHit')],
    raw_row: Number(r[idx('RawRow')])
  }));

  if (!approved.length) { SpreadsheetApp.getUi().alert('Nothing approved.'); return; }

  const res = UrlFetchApp.fetch(SYNC_URL, {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-API-Key': API_KEY },   // ← MUST be here
    payload: JSON.stringify({ rows: approved }),
    muteHttpExceptions: true
  });


  if (res.getResponseCode() !== 200) {
    SpreadsheetApp.getUi().alert('Sync error: ' + res.getContentText());
    return;
  }

  // Move approved to Published
  let pub = ss.getSheetByName(SHEET_PUB);
  if (!pub) pub = ss.insertSheet(SHEET_PUB);
  const pubHeader = header.filter(h => h !== 'Approved');
  if (pub.getLastRow() === 0) pub.getRange(1,1,1,pubHeader.length).setValues([pubHeader]);

  const approvedRows = vals.slice(1).filter(r => r[idx('Approved')] === true);
  if (approvedRows.length) {
    const cleaned = approvedRows.map(r => r.filter((_,i) => header[i] !== 'Approved'));
    pub.getRange(pub.getLastRow()+1, 1, cleaned.length, cleaned[0].length).setValues(cleaned);
  }

  // Clear Approved marks
  const checkCol = 1; // "Approved"
  const last = sh.getLastRow();
  if (last > 1) sh.getRange(2, checkCol, last-1, 1).clearContent();

  SpreadsheetApp.getUi().alert(`Published ${approved.length} rows to MySQL.`);
}


/** Menu handler: converts BankRaw_Statement into a fresh sheet with RAW_HEADER */
function menuNormalizeBankRaw() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActive();
  if (!ss) {
    ui.alert('No active spreadsheet found. Please open a spreadsheet and try again.');
    return;
  }
  
  try {
    const { outName, rowCount } = normalizeBankRawStatement();
    ui.alert('Done', `Created "${outName}" with ${rowCount} rows.`, ui.ButtonSet.OK);
  } catch (e) {
    ui.alert('Normalization failed', String(e && e.message ? e.message : e), ui.ButtonSet.OK);
  }
}

/** Core converter: BankRaw_Statement → new sheet with [Date, Description, Amount, Balance, Account, Currency] */
function normalizeBankRawStatement() {
  const ss  = SpreadsheetApp.getActive();
  const src = ss.getSheetByName(SHEET_BANKRAW);
  if (!src) throw new Error(`Sheet "${SHEET_BANKRAW}" not found.`);

  const values = src.getDataRange().getValues();
  if (values.length < 2) throw new Error('No data rows found in BankRaw_Statement.');

  // Build column index from header row (robust to naming differences)
  const headers = values[0].map(h => String(h).trim());
  const idx = brs_buildIndex(headers, BANK_HEADER_SYNONYMS);

  if (idx.date < 0)     throw new Error('Could not find a Date column.');
  if (idx.desc < 0)     throw new Error('Could not find a Narration/Description column.');
  if (idx.balance < 0)  throw new Error('Could not find a Balance/Closing Balance column.');
  if (idx.withdraw < 0 && idx.deposit < 0 && idx.amount < 0)
    throw new Error('Could not find Withdrawal/Deposit/Amount columns.');

  const outHeader = RAW_HEADER; // ['Date','Description','Amount','Balance','Account','Currency']
  const outRows = [];

  for (let r = 1; r < values.length; r++) {
    const row = values[r];
    // skip fully empty rows
    if (row.every(v => v === '' || v === null)) continue;

    const date = brs_coerceDate(row[idx.date]);
    const desc = brs_safeStr(row[idx.desc]);
    const amt  = brs_computeAmount(row, idx);
    const bal  = brs_toNumber(row[idx.balance]);

    // skip rows with neither date nor description nor any numeric value
    const skip = !date && !desc && (amt === null || amt === 0) && (bal === null || bal === 0);
    if (skip) continue;

    outRows.push([
      date || '',
      desc,
      amt ?? '',
      bal ?? '',
      NORMALIZE_ACCOUNT,
      NORMALIZE_CURRENCY
    ]);
  }

  if (outRows.length === 0) throw new Error('No usable rows after parsing.');

  // Create a fresh output sheet
  const ts = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyyMMdd_HHmmss');
  const outName = `${NORMALIZE_OUTPUT_PREFIX}_${SHEET_BANKRAW}_${ts}`;
  const out = ss.insertSheet(outName);

  // Write header + rows
  out.getRange(1,1,1,outHeader.length).setValues([outHeader]);
  out.getRange(2,1,outRows.length,outHeader.length).setValues(outRows);

  // Nice formatting
  out.getRange(1,1,1,outHeader.length).setFontWeight('bold').setBackground('#f5f5f5');
  out.autoResizeColumns(1, outHeader.length);

  const n = outRows.length;
  out.getRange(2,1,n,1).setNumberFormat('yyyy-mm-dd');               // Date
  out.getRange(2,3,n,1).setNumberFormat('#,##0.00;[Red]-#,##0.00');  // Amount
  out.getRange(2,4,n,1).setNumberFormat('#,##0.00;[Red]-#,##0.00');  // Balance

  return { outName, rowCount: n };
}

/* =========== Helpers (names prefixed with brs_ to avoid collisions) =========== */
function brs_buildIndex(headers, syn) {
  const find = names => {
    // exact match
    for (const n of names) {
      const i = headers.findIndex(h => h.toLowerCase() === String(n).toLowerCase());
      if (i >= 0) return i;
    }
    // contains
    for (const n of names) {
      const needle = String(n).toLowerCase();
      const i = headers.findIndex(h => h.toLowerCase().includes(needle));
      if (i >= 0) return i;
    }
    return -1;
  };
  return {
    date:     find(syn.date),
    desc:     find(syn.desc),
    withdraw: find(syn.withdraw),
    deposit:  find(syn.deposit),
    balance:  find(syn.balance),
    amount:   find(syn.amount),
    side:     find(syn.side)
  };
}

function brs_computeAmount(row, idx) {
  // Prefer separate deposit/withdraw columns when present
  const wd = idx.withdraw >= 0 ? brs_toNumber(row[idx.withdraw]) : null;
  const dp = idx.deposit  >= 0 ? brs_toNumber(row[idx.deposit])  : null;

  if (brs_isNum(dp) && Math.abs(dp) > 0) return Math.abs(dp);       // +deposit
  if (brs_isNum(wd) && Math.abs(wd) > 0) return -Math.abs(wd);      // -withdraw

  // Fallback: single Amount column, possibly with a Dr/Cr indicator
  if (idx.amount >= 0) {
    let a = brs_toNumber(row[idx.amount]);
    if (!brs_isNum(a)) return null;
    if (idx.side >= 0) {
      const s = brs_safeStr(row[idx.side]).toLowerCase();
      if (s.includes('dr') || s.includes('debit'))  a = -Math.abs(a);
      if (s.includes('cr') || s.includes('credit')) a =  Math.abs(a);
    }
    return a;
  }
  return null;
}

function brs_toNumber(v) {
  if (v === '' || v === null || v === undefined) return null;
  if (typeof v === 'number') return v;
  const s = String(v).replace(/[, ]/g, '');
  const n = parseFloat(s);
  return isNaN(n) ? null : n;
}

// ---- DMY-first date parsing (India style) ----
function brs_coerceDate(v) {
  if (v instanceof Date) return v;

  const s = brs_safeStr(v);
  if (!s) return null;

  // 1) dd/mm/yy or dd-mm-yy or dd.mm.yy (also supports yyyy as last part)
  let m = s.match(/^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})$/);
  if (m) {
    const d = parseInt(m[1], 10);
    const mo = parseInt(m[2], 10);
    const y = brs_parseYear(m[3]);
    return brs_makeDate(y, mo, d);
  }

  // 2) yyyy-mm-dd (ISO-ish)
  m = s.match(/^(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})$/);
  if (m) {
    return brs_makeDate(parseInt(m[1],10), parseInt(m[2],10), parseInt(m[3],10));
  }

  // 3) dd-MMM-yy or dd MMM yyyy (e.g., 01-May-2025, 1 May 25)
  m = s.match(/^(\d{1,2})[ \-]([A-Za-z]{3,})[ \-](\d{2,4})$/);
  if (m) {
    const d = parseInt(m[1], 10);
    const mo = brs_monthFromName(m[2]);
    const y = brs_parseYear(m[3]);
    return brs_makeDate(y, mo, d);
  }

  // 4) Fallback: if it looks like D/M/Y (first token <=31 & second <=12), assume DMY
  m = s.match(/^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})/);
  if (m && parseInt(m[1],10) <= 31 && parseInt(m[2],10) <= 12) {
    const d = parseInt(m[1], 10);
    const mo = parseInt(m[2], 10);
    const y = brs_parseYear(m[3]);
    return brs_makeDate(y, mo, d);
  }

  // Last resort (may misinterpret ambiguous strings)
  const dflt = new Date(s);
  return isNaN(dflt.getTime()) ? null : dflt;
}

// Two-digit year pivot: 00–69 => 2000–2069, 70–99 => 1970–1999
function brs_parseYear(yStr) {
  let y = parseInt(yStr, 10);
  if (y < 100) y += (y <= 69 ? 2000 : 1900);
  return y;
}

function brs_monthFromName(name) {
  const m = name.toLowerCase().slice(0,3);
  const map = { jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12 };
  return map[m] || NaN;
}

// Builds a true Date or returns null if invalid (e.g., 31/11)
function brs_makeDate(y, m, d) {
  if (!y || m < 1 || m > 12 || d < 1 || d > 31) return null;
  const dt = new Date(y, m - 1, d);
  return (dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d) ? dt : null;
}


function brs_safeStr(v) {
  return v === null || v === undefined ? '' : String(v).trim();
}

function brs_isNum(n) {
  return typeof n === 'number' && !isNaN(n);
}

// ====== RULE LEARNING FUNCTIONS ======

function menuLearnRules() {
  const ui = SpreadsheetApp.getUi();
  
  // Ask for confirmation
  const response = ui.alert(
    'Learn New Rules',
    'This will analyze verified transactions in the database and learn new categorization rules.\n\nDo you want to continue?',
    ui.ButtonSet.YES_NO
  );
  
  if (response !== ui.Button.YES) {
    return;
  }
  
  try {
    const result = learnRulesFromDatabase();
    
    if (result.ok) {
      if (result.rules_learned > 0) {
        // Show detailed results
        let message = `✅ Successfully learned ${result.rules_learned} new rules!\n\n`;
        message += 'New Rules:\n';
        
        result.new_rules.forEach((rule, index) => {
          message += `${index + 1}. ${rule.name}\n`;
          message += `   Keywords: ${rule.keywords.join(', ')}\n`;
          message += `   Category: ${rule.main_category} → ${rule.sub_category}\n`;
          message += `   Frequency: ${rule.frequency} transactions\n`;
          message += `   Confidence: ${rule.confidence.toFixed(2)}\n\n`;
        });
        
        ui.alert('Rule Learning Complete', message, ui.ButtonSet.OK);
      } else {
        ui.alert('Rule Learning Complete', 'No new rules found to learn. The system may already have good coverage for your current data.', ui.ButtonSet.OK);
      }
    } else {
      ui.alert('Rule Learning Failed', `Error: ${result.message}`, ui.ButtonSet.OK);
    }
  } catch (error) {
    ui.alert('Rule Learning Error', `Unexpected error: ${error.toString()}`, ui.ButtonSet.OK);
  }
}

function menuRuleStats() {
  const ui = SpreadsheetApp.getUi();
  
  try {
    const stats = getRuleStatistics();
    
    if (stats.ok) {
      let message = '📊 RULE STATISTICS\n\n';
      message += `Total Rules: ${stats.total_rules}\n\n`;
      message += 'Database Statistics:\n';
      message += `• Total Transactions: ${stats.database_stats.total_transactions}\n`;
      message += `• Verified Transactions: ${stats.database_stats.verified_transactions}\n`;
      message += `• High Confidence: ${stats.database_stats.high_confidence_transactions}\n\n`;
      
      if (stats.top_categories && stats.top_categories.length > 0) {
        message += 'Top Categories:\n';
        stats.top_categories.forEach((cat, index) => {
          message += `${index + 1}. ${cat.category}: ${cat.count} transactions\n`;
        });
      }
      
      ui.alert('Rule Statistics', message, ui.ButtonSet.OK);
    } else {
      ui.alert('Statistics Error', `Error: ${stats.message}`, ui.ButtonSet.OK);
    }
  } catch (error) {
    ui.alert('Statistics Error', `Unexpected error: ${error.toString()}`, ui.ButtonSet.OK);
  }
}

function learnRulesFromDatabase() {
  try {
    const response = UrlFetchApp.fetch(LEARN_RULES_URL, {
      method: 'POST',
      contentType: 'application/json',
      headers: { 'X-API-Key': API_KEY },
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() !== 200) {
      return {
        ok: false,
        message: `HTTP ${response.getResponseCode()}: ${response.getContentText()}`
      };
    }
    
    return JSON.parse(response.getContentText());
  } catch (error) {
    return {
      ok: false,
      message: `Network error: ${error.toString()}`
    };
  }
}

function getRuleStatistics() {
  try {
    const response = UrlFetchApp.fetch(RULE_STATS_URL, {
      method: 'GET',
      headers: { 'X-API-Key': API_KEY },
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() !== 200) {
      return {
        ok: false,
        message: `HTTP ${response.getResponseCode()}: ${response.getContentText()}`
      };
    }
    
    return JSON.parse(response.getContentText());
  } catch (error) {
    return {
      ok: false,
      message: `Network error: ${error.toString()}`
    };
  }
}

function menuClearCache() {
  const ui = SpreadsheetApp.getUi();
  
  try {
    const result = clearRulesCache();
    
    if (result.ok) {
      ui.alert('Cache Cleared', result.message, ui.ButtonSet.OK);
    } else {
      ui.alert('Cache Clear Failed', `Error: ${result.message}`, ui.ButtonSet.OK);
    }
  } catch (error) {
    ui.alert('Cache Clear Error', `Unexpected error: ${error.toString()}`, ui.ButtonSet.OK);
  }
}

function clearRulesCache() {
  try {
    const response = UrlFetchApp.fetch(CLEAR_CACHE_URL, {
      method: 'POST',
      contentType: 'application/json',
      headers: { 'X-API-Key': API_KEY },
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() !== 200) {
      return {
        ok: false,
        message: `HTTP ${response.getResponseCode()}: ${response.getContentText()}`
      };
    }
    
    return JSON.parse(response.getContentText());
  } catch (error) {
    return {
      ok: false,
      message: `Network error: ${error.toString()}`
    };
  }
}
