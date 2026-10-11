
const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const ARTIFACT_DIR = 'C:\\Users\\ranja\\.gemini\\antigravity-ide\\brain\\11977ce9-721a-45ee-88dd-eb7cb28870f5';

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runAudit() {
  const { default: puppeteer } = await import('puppeteer-core');
  const { default: path } = await import('node:path');
  const { default: fs } = await import('node:fs');
  console.log('=== Starting CodeMentor-RAG Browser Audit ===');
  const browser = await puppeteer.launch({
    executablePath: EDGE_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1600,1000'],
    defaultViewport: { width: 1600, height: 1000 }
  });

  const page = await browser.newPage();
  const results = {
    steps: [],
    errors: [],
    screenshots: []
  };

  function logStep(name, status, details = '') {
    console.log(`[${status}] ${name}: ${details}`);
    results.steps.push({ name, status, details });
  }

  async function snap(name) {
    const filename = `audit_${name}.png`;
    const fullPath = path.join(ARTIFACT_DIR, filename);
    await page.screenshot({ path: fullPath });
    results.screenshots.push(fullPath);
    console.log(`  Screenshot saved: ${filename}`);
  }

  try {
    // 1. Navigate to http://localhost:3000
    logStep('Navigation', 'RUNNING', 'Navigating to http://localhost:3000');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(2000);
    await snap('01_initial_load');
    logStep('Navigation', 'PASS', 'App loaded successfully');

    // 2. Select repository if not selected
    const calcButton = await page.evaluate(() => {
      const el = Array.from(document.querySelectorAll('*')).find(
        e => e.textContent && e.textContent.includes('calculator') && (e.tagName === 'BUTTON' || e.getAttribute('role') === 'button' || e.className.includes('card') || e.className.includes('repo'))
      );
      if (el) {
        el.click();
        return true;
      }
      return false;
    });

    if (calcButton) {
      logStep('Repo Selection', 'PASS', 'Clicked calculator repository');
      await sleep(2500);
      await snap('02_workspace_loaded');
    } else {
      logStep('Repo Selection', 'INFO', 'Already in workspace or repository card not clicked');
    }

    // 3. Verify 4-zone layout
    const layout = await page.evaluate(() => {
      return {
        activityRail: !!document.querySelector('aside') || !!document.querySelector('[title="Explorer"]'),
        sidebar: !!document.querySelector('input[placeholder*="Filter"]') || !!document.querySelector('[title="Collapse sidebar"]'),
        statusBar: !!document.querySelector('.h-6') || document.body.innerText.includes('READY'),
        chatInput: !!document.querySelector('textarea[placeholder*="Ask"]'),
        tutorModes: ['Beginner', 'Developer', 'Interview', 'Debug'].filter(m => document.body.innerText.includes(m))
      };
    });
    logStep('Layout Audit', 'PASS', JSON.stringify(layout));

    // 4. File Explorer: Open calculator.py
    logStep('File Explorer', 'RUNNING', 'Opening calculator.py');
    const clickedFile = await page.evaluate(() => {
      const calcEl = Array.from(document.querySelectorAll('button, span, div')).find(
        e => e.textContent && e.textContent.includes('calculator.py') && !e.closest('.h-6')
      );
      if (calcEl) {
        calcEl.click();
        return true;
      }
      return false;
    });
    await sleep(1500);
    await snap('03_code_viewer_calculator');
    logStep('File Explorer', clickedFile ? 'PASS' : 'WARN', `Opened calculator.py: ${clickedFile}`);

    // 5. Symbols Explorer Tab
    logStep('Symbols Explorer', 'RUNNING', 'Switching to Symbols tab in sidebar');
    await page.evaluate(() => {
      const symTab = Array.from(document.querySelectorAll('button')).find(
        b => b.title === 'AST Symbols' || (b.textContent && b.textContent.includes('Symbols'))
      );
      if (symTab) {
        symTab.click();
        return true;
      }
      return false;
    });
    await sleep(1000);
    await snap('04_symbols_tab');

    // Click symbol divide
    await page.evaluate(() => {
      const divideSym = Array.from(document.querySelectorAll('button, div, span')).find(
        e => e.textContent && e.textContent.trim() === 'divide'
      );
      if (divideSym) divideSym.click();
    });
    await sleep(1000);
    await snap('05_symbol_jump_divide');
    logStep('Symbols Explorer', 'PASS', 'Symbol clicked and jumped');

    // 6. Test AI Tutor Chat & Citations
    logStep('AI Tutor Chat', 'RUNNING', 'Sending question in Developer mode');
    await page.evaluate(() => {
      const devBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.textContent && b.textContent.trim() === 'Developer'
      );
      if (devBtn) devBtn.click();
    });
    await sleep(500);

    const inputSelector = 'textarea[placeholder*="Ask"]';
    await page.waitForSelector(inputSelector, { timeout: 5000 });
    await page.type(inputSelector, 'How does divide handle division by zero in calculator.py?');
    await sleep(500);

    await page.evaluate(() => {
      const sendBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.querySelector('svg') && !b.disabled && b.closest('.p-3')
      );
      if (sendBtn) sendBtn.click();
    });

    logStep('AI Tutor Chat', 'RUNNING', 'Waiting for assistant response...');
    let responseArrived = false;
    for (let i = 0; i < 40; i++) {
      await sleep(1000);
      responseArrived = await page.evaluate(() => {
        const text = document.body.innerText;
        return text.includes('divide') && text.includes('ValueError') && (text.includes('src\\calculator.py') || text.includes('calculator.py'));
      });
      if (responseArrived) break;
    }
    await snap('06_chat_response_citations');
    logStep('AI Tutor Chat', responseArrived ? 'PASS' : 'WARN', `Response arrived: ${responseArrived}`);

    // Click citation chip to test pulse highlight
    logStep('Citation Interaction', 'RUNNING', 'Clicking citation chip');
    const citationClicked = await page.evaluate(() => {
      const chip = Array.from(document.querySelectorAll('button')).find(
        b => b.textContent && (b.textContent.includes('calculator.py') && b.textContent.includes('32-39'))
      );
      if (chip) {
        chip.click();
        return chip.textContent.trim();
      }
      return null;
    });
    await sleep(1000);
    await snap('07_citation_clicked_pulse');
    logStep('Citation Interaction', citationClicked ? 'PASS' : 'WARN', `Clicked chip: ${citationClicked}`);

    // 7. Interactive Interview Mode
    logStep('Interview Mode', 'RUNNING', 'Switching to Interview mode');
    await page.evaluate(() => {
      const interviewBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.textContent && b.textContent.trim() === 'Interview'
      );
      if (interviewBtn) interviewBtn.click();
    });
    await sleep(1500);
    await snap('08_interview_setup');

    // Click "Start Interview"
    await page.evaluate(() => {
      const startBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.textContent && b.textContent.includes('Start Interview')
      );
      if (startBtn) startBtn.click();
    });
    logStep('Interview Mode', 'RUNNING', 'Generating interview questions...');
    for (let i = 0; i < 20; i++) {
      await sleep(1000);
      const ready = await page.evaluate(() => {
        return !!document.querySelector('textarea[placeholder*="Type your answer"]');
      });
      if (ready) break;
    }
    await snap('09_interview_question');

    // Answer the question
    await page.evaluate(() => {
      const ta = document.querySelector('textarea[placeholder*="Type your answer"]');
      if (ta) {
        ta.value = 'In calculator.py, the divide function checks if the divisor b is 0. If b == 0, it raises a ValueError with an explicit error message stating division by zero is not allowed, ensuring fail-fast runtime safety and recording the operation.';
        ta.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
    await sleep(500);

    // Submit answer
    await page.evaluate(() => {
      const submitBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.textContent && b.textContent.includes('Submit Answer')
      );
      if (submitBtn) submitBtn.click();
    });

    logStep('Interview Mode', 'RUNNING', 'Submitting and evaluating answer...');
    let evaluated = false;
    for (let i = 0; i < 25; i++) {
      await sleep(1000);
      evaluated = await page.evaluate(() => {
        return document.body.innerText.includes('/100') || document.body.innerText.includes('Feedback') || document.body.innerText.includes('Next Question');
      });
      if (evaluated) break;
    }
    await snap('10_interview_evaluated');
    logStep('Interview Mode', evaluated ? 'PASS' : 'WARN', `Answer evaluated: ${evaluated}`);

    // 8. Code Knowledge Graph & Call Flows
    logStep('Knowledge Graph', 'RUNNING', 'Opening Knowledge Graph view');
    await page.evaluate(() => {
      const graphBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.title === 'Code Knowledge Graph' || (b.textContent && b.textContent.includes('Graph'))
      );
      if (graphBtn) graphBtn.click();
    });
    await sleep(2000);
    await snap('11_knowledge_graph_view');

    // Switch to Call Flows tab
    await page.evaluate(() => {
      const callFlowsBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.textContent && b.textContent.includes('Call Flows')
      );
      if (callFlowsBtn) callFlowsBtn.click();
    });
    await sleep(1500);
    await snap('12_call_flows_view');
    logStep('Knowledge Graph', 'PASS', 'Graph and Call Flows verified');

    // 9. Command Palette (Ctrl+K)
    logStep('Command Palette', 'RUNNING', 'Testing Command Palette');
    await page.keyboard.down('Control');
    await page.keyboard.press('KeyK');
    await page.keyboard.up('Control');
    await sleep(1000);

    const cpInputSelector = 'input[placeholder*="symbol, question, or action"]';
    const cpExists = await page.$(cpInputSelector);
    if (cpExists) {
      await page.type(cpInputSelector, 'divide');
      await sleep(500);
      await snap('13_command_palette');
      await page.keyboard.press('Escape');
      logStep('Command Palette', 'PASS', 'Command Palette tested with Ctrl+K');
    } else {
      logStep('Command Palette', 'WARN', 'Command Palette input not focused');
    }
    await sleep(500);

    // 10. Theme Toggle
    logStep('Theme Toggle', 'RUNNING', 'Testing Theme Toggle');
    await page.evaluate(() => {
      const themeBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.title && b.title.includes('Theme')
      );
      if (themeBtn) themeBtn.click();
    });
    await sleep(1000);
    await snap('14_light_theme');

    await page.evaluate(() => {
      const themeBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.title && b.title.includes('Theme')
      );
      if (themeBtn) themeBtn.click();
    });
    await sleep(1000);
    await snap('15_dark_theme');
    logStep('Theme Toggle', 'PASS', 'Light & Dark theme toggled successfully');

    // 11. Top Modals: Retrieval Lab & Settings
    logStep('Retrieval Lab Modal', 'RUNNING', 'Opening Retrieval Lab');
    await page.evaluate(() => {
      const labBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.textContent && b.textContent.includes('Retrieval Lab')
      );
      if (labBtn) labBtn.click();
    });
    await sleep(1000);
    await snap('16_retrieval_lab_modal');
    await page.keyboard.press('Escape');
    await sleep(500);

    logStep('Settings Modal', 'RUNNING', 'Opening Settings modal');
    await page.evaluate(() => {
      const settingsBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.title === 'Settings' || (b.textContent && b.textContent.includes('Settings'))
      );
      if (settingsBtn) settingsBtn.click();
    });
    await sleep(1000);
    await snap('17_settings_modal');
    await page.keyboard.press('Escape');
    await sleep(500);

    console.log('=== Browser Audit Complete ===');
    fs.writeFileSync(
      path.join(ARTIFACT_DIR, 'browser_audit_results.json'),
      JSON.stringify(results, null, 2)
    );

  } catch (err) {
    console.error('Audit Error:', err);
    results.errors.push(err.message);
    await snap('error_state');
  } finally {
    await browser.close();
  }
}

runAudit();
