document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('request-input');
    const submitBtn = document.getElementById('submit-btn');
    const resultsPanel = document.getElementById('results-panel');
    const loadingOverlay = document.getElementById('loading-overlay');
    const scenarioBtns = document.querySelectorAll('.scenario-btn');
    const agentStatus = document.getElementById('agent-status');

    // Scenarios mapping from the dataset
    const scenarios = {
        "normal": "Meridian DataVault Inc. 2x PRD-001 by 2026-10-15. Installation required.",
        "multi": "Axiom Manufacturing Group. 1x PRD-002, 5x PRD-003 by 2026-11-01. No installation.",
        "clarification": "Ironclad Defence Systems. 1x PRD-004 by tomorrow.",
        "unfulfillable": "Harken Retail Solutions. 100x PRD-003 by 2026-12-01."
    };

    scenarioBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            input.value = scenarios[btn.dataset.scenario];
        });
    });

    let loadingInterval;

    submitBtn.addEventListener('click', async () => {
        const text = input.value.trim();
        if (!text) return;

        submitBtn.disabled = true;
        submitBtn.textContent = 'Processing...';

        loadingOverlay.style.display = 'flex';
        resultsPanel.style.display = 'none';

        // Animate processing steps
        const steps = document.querySelectorAll('.loading-steps span');
        let currentStep = 0;
        steps.forEach(s => s.className = '');
        if (steps.length > 0) steps[0].className = 'active';

        loadingInterval = setInterval(() => {
            currentStep = (currentStep + 1) % steps.length;
            steps.forEach(s => s.className = '');
            steps[currentStep].className = 'active';
        }, 1200);

        try {
            const response = await fetch('/api/quote', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ raw_request: text })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Failed to process request');
            }

            const data = await response.json();
            renderResults(data);

            resultsPanel.style.display = 'block';

            // Smooth scroll to results
            setTimeout(() => {
                resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);

        } catch (error) {
            alert(`Error: ${error.message}`);
        } finally {
            clearInterval(loadingInterval);
            loadingOverlay.style.display = 'none';
            submitBtn.disabled = false;
            submitBtn.textContent = 'Analyze Request';
        }
    });

    const resetBtn = document.getElementById('reset-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            resultsPanel.style.display = 'none';
            input.value = '';
            document.querySelector('.request-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
            input.focus();
        });
    }

    function renderResults(data) {
        // Reset pipeline styling. Do not auto-claim completion.
        document.querySelectorAll('.stage').forEach(el => {
            el.className = 'stage';
        });

        const riskResult = data.original_quote_risk_result || {};
        const decision = riskResult.quote_decision || 'UNKNOWN';

        // 1. BANNER DECISION
        const banner = document.getElementById('decision-banner');
        const decisionTitle = document.getElementById('decision-title');
        const decisionExp = document.getElementById('decision-explanation');
        const decisionIcon = document.getElementById('decision-icon');

        if (decision === 'QUOTE_READY') {
            banner.className = 'decision-banner banner-green';
            decisionTitle.textContent = 'QUOTE READY';
            decisionExp.textContent = 'The request passed the required validation checks and is ready for quotation.';
            decisionIcon.textContent = '🟢';
        } else if (decision === 'CUSTOMER_CLARIFICATION_REQUIRED') {
            banner.className = 'decision-banner banner-yellow';
            decisionTitle.textContent = 'CLARIFICATION REQUIRED';
            decisionExp.textContent = 'Additional customer information is required before the quotation can be finalized.';
            decisionIcon.textContent = '🟡';
        } else if (decision === 'REQUEST_CANNOT_BE_FULFILLED') {
            banner.className = 'decision-banner banner-red';
            decisionTitle.textContent = 'REQUEST CANNOT BE FULFILLED';
            decisionExp.textContent = 'The request violates policy, inventory limits, or cannot be fulfilled as specified.';
            decisionIcon.textContent = '🔴';
        } else if (decision === 'HUMAN_APPROVAL_REQUIRED') {
            banner.className = 'decision-banner banner-orange';
            decisionTitle.textContent = 'HUMAN APPROVAL REQUIRED';
            decisionExp.textContent = 'This request requires human review before it can proceed.';
            decisionIcon.textContent = '🟠';
        } else {
            banner.className = 'decision-banner';
            decisionTitle.textContent = decision.replace(/_/g, ' ');
            decisionExp.textContent = 'Outcome could not be mapped to standard UI.';
            decisionIcon.textContent = '⚪';
        }

        // 2. FINANCIAL SUMMARY
        const total = parseFloat(riskResult.financial_summary_total);
        if (!isNaN(total) && riskResult.financial_summary_total !== null) {
            document.getElementById('financial-total').textContent = '₹' + total.toLocaleString('en-IN', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        } else {
            document.getElementById('financial-total').textContent = '—';
        }

        // 3. DETAILS
        document.getElementById('customer-ref').textContent = riskResult.customer_reference || '—';

        // In the Phase 3 schema, there is no top-level delivery date inside QuoteRiskResult natively
        // unless passed down, but we will check if it's there. The user requested:
        // "Only display fields that are actually available."
        // We will just leave them blank if not provided in the QuoteRiskResult parsed object.
        // Wait, QuoteRiskResult only has request_id, customer_reference, quote_decision, risk_indicators, reasons, financial_summary_total, approval_requirement, issues
        // If the backend doesn't send delivery date in QuoteRiskResult, we can't show it here.
        // We will just check if they exist.
        if (data.original_request_understanding) {
            const delDate = data.original_request_understanding.requested_delivery_date;
            document.getElementById('delivery-date').textContent = delDate ? delDate : '—';

            const instReq = data.original_request_understanding.installation_required;
            if (instReq === true) {
                document.getElementById('installation').textContent = 'Required';
            } else if (instReq === false) {
                document.getElementById('installation').textContent = 'Not required';
            } else {
                document.getElementById('installation').textContent = '—';
            }

            const reqItems = document.getElementById('requested-items');
            reqItems.innerHTML = '';
            (data.original_request_understanding.requested_items || []).forEach(item => {
                const div = document.createElement('div');
                div.textContent = `${item.quantity || '?'}x ${item.product_id || item.raw_product_reference || 'Unknown'}`;
                reqItems.appendChild(div);
            });
        }

        // 4. ISSUES / CLARIFICATION
        const issuesSection = document.getElementById('issues-section');
        const issuesList = document.getElementById('issues-list');
        const reasonsList = document.getElementById('reasons-list');
        issuesList.innerHTML = '';
        reasonsList.innerHTML = '';

        let hasIssues = false;
        if (riskResult.issues && riskResult.issues.length > 0) {
            hasIssues = true;
            riskResult.issues.forEach(issue => {
                const li = document.createElement('li');
                li.textContent = issue;
                issuesList.appendChild(li);
            });
        }
        if (riskResult.reasons && riskResult.reasons.length > 0) {
            hasIssues = true;
            riskResult.reasons.forEach(reason => {
                const li = document.createElement('li');
                li.textContent = reason;
                reasonsList.appendChild(li);
            });
        }
        issuesSection.style.display = hasIssues ? 'block' : 'none';

        // 5. RISK INDICATORS
        const riskList = document.getElementById('risk-indicators');
        riskList.innerHTML = '';
        const riskSection = document.getElementById('risk-section');
        if (riskResult.risk_indicators && riskResult.risk_indicators.length > 0) {
            riskSection.style.display = 'block';
            riskResult.risk_indicators.forEach(risk => {
                const li = document.createElement('li');
                li.textContent = risk;
                riskList.appendChild(li);
            });
        } else {
            riskSection.style.display = 'none';
        }

        // 6. PIPELINE & APPROVAL
        const stageApproval = document.getElementById('stage-approval');
        const approvalPanel = document.getElementById('approval-panel');

        if (data.status === 'PAUSED_FOR_APPROVAL' || decision === 'HUMAN_APPROVAL_REQUIRED') {
            stageApproval.textContent = '5. Human Approval (Pending)';
            stageApproval.className = 'stage pending';
            approvalPanel.style.display = 'block';
        } else if (data.status === 'NO_APPROVAL_REQUIRED' || decision === 'CUSTOMER_CLARIFICATION_REQUIRED' || decision === 'REQUEST_CANNOT_BE_FULFILLED' || decision === 'QUOTE_READY') {
            stageApproval.textContent = '5. Human Approval (Not Required)';
            stageApproval.className = 'stage not-required';
            approvalPanel.style.display = 'none';
        } else {
            stageApproval.textContent = '5. Human Approval';
            stageApproval.className = 'stage';
            approvalPanel.style.display = 'none';
        }
    }

    // Check health on load
    fetch('/health').then(res => res.json()).then(data => {
        if(data.endpoint_configured) {
            agentStatus.textContent = "Agent Connected";
            document.querySelector('.status-dot').style.backgroundColor = 'var(--green-text)';
        } else {
            agentStatus.textContent = "Agent Disconnected (Configure ENV)";
            document.querySelector('.status-dot').style.backgroundColor = 'var(--red-text)';
        }
    }).catch(() => {
        agentStatus.textContent = "Server Offline";
    });
});
