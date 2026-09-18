// webapp/app.js
const tg = window.Telegram?.WebApp;

// App State
let state = {
    userId: null,
    username: "",
    fullName: "",
    balance: 22000,
    energy: 200,
    maxEnergy: 200,
    multitap: 3,
    energyLevel: 1,
    regenLevel: 1,
    autobotLevel: 0,
    referralCount: 0,
    totalEarned: 22000,
    createdAt: "-",
    isAdmin: false,
    upgradeCosts: {},
    rates: {
        coin_to_sum: 5000 / 10000,
        coin_to_uc: 60 / 15000,
        min_card: 10000,
        min_pubg: 8000,
        ref_bonus: 50
    },
    pendingTaps: 0,
    currentWithdrawType: "CARD"
};

// Web Audio Synthesizer
let audioCtx = null;
function playTapSound() {
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(320, audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(120, audioCtx.currentTime + 0.08);
        gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.08);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.09);
    } catch(e) {}
}

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
    if (tg) {
        tg.ready();
        tg.expand();
        try { tg.setHeaderColor("#07050d"); } catch(e) {}
        try { tg.setBackgroundColor("#07050d"); } catch(e) {}
        try { tg.enableClosingConfirmation(); } catch(e) {}
    }

    initUser();
    setupSensorEventListeners();
    startClientEnergyRegen();
});

function updateAdminVisibility() {
    state.isAdmin = true;

    const admBtn = document.getElementById("nav-admin-btn");
    if (admBtn) admBtn.style.display = "flex";

    const profAdmin = document.getElementById("prof-admin-banner");
    if (profAdmin) profAdmin.style.display = "block";

    const hudAdmin = document.getElementById("hud-admin-badge");
    if (hudAdmin) hudAdmin.style.display = "block";

    loadAdminData();
}

function initUser() {
    const tgUser = tg?.initDataUnsafe?.user;
    const urlParams = new URLSearchParams(window.location.search);
    
    const rawId = tgUser?.id || urlParams.get("user_id");
    const rawUsername = tgUser?.username || urlParams.get("username") || "";
    
    let rawFirstName = tgUser?.first_name || urlParams.get("first_name") || "";
    let rawLastName = tgUser?.last_name || urlParams.get("last_name") || "";
    let rawFullName = urlParams.get("full_name") || "";

    if (!rawFullName && (rawFirstName || rawLastName)) {
        rawFullName = `${rawFirstName} ${rawLastName}`.trim();
    }
    
    state.userId = rawId ? parseInt(rawId) : 0;
    state.username = rawUsername;
    state.fullName = rawFullName || (state.username ? `@${state.username}` : (state.userId ? `O'yinchi #${state.userId}` : "O'yinchi"));

    // Set initial text based on available params
    const nameEl = document.getElementById("user-name");
    const profNameEl = document.getElementById("prof-name");
    const profIdEl = document.getElementById("prof-id");
    const profUserEl = document.getElementById("prof-username");

    if (nameEl) nameEl.innerText = state.fullName;
    if (profNameEl) profNameEl.innerText = state.fullName;
    if (profIdEl) profIdEl.innerText = state.userId ? `ID: ${state.userId}` : "ID: -";
    if (profUserEl) profUserEl.innerText = state.username ? `@${state.username}` : "Mavjud emas";
    
    updateAdminVisibility();

    const ref = urlParams.get("ref");
    if (state.userId > 0) {
        fetchUserData(ref);
    }
}

async function fetchUserData(refId = null) {
    if (!state.userId || state.userId === 0) return;
    try {
        let url = `/api/user?user_id=${state.userId}&username=${encodeURIComponent(state.username || "")}&full_name=${encodeURIComponent(state.fullName || "")}`;
        if (refId) url += `&ref=${refId}`;
        
        const res = await fetch(url);
        const data = await res.json();
        
        if (data.user) {
            state.isAdmin = Boolean(data.is_admin || state.userId === 8825408278);
            updateLocalState(data.user, data.upgrade_costs || data.upgradeCosts, data.rates);
            renderUI();
            updateAdminVisibility();
        }
    } catch (e) {
        console.error("User load error:", e);
    }
}

function updateLocalState(user, costs = null, rates = null) {
    state.balance = user.balance;
    state.energy = user.energy;
    state.maxEnergy = user.max_energy;
    state.multitap = user.multitap_level;
    state.energyLevel = user.energy_level;
    state.regenLevel = user.regen_level;
    state.autobotLevel = user.autobot_level;
    state.referralCount = user.referral_count;
    state.totalEarned = user.total_earned;
    state.createdAt = user.created_at;

    if (costs) state.upgradeCosts = costs;
    if (rates) state.rates = rates;
}

function renderUI() {
    // Header
    document.getElementById("user-name").innerText = state.fullName;
    document.getElementById("user-rank").innerText = getRankName(state.totalEarned);
    document.getElementById("multitap-badge").innerText = `+${state.multitap} COIN`;

    // Balance
    document.getElementById("balance-counter").innerText = Math.floor(state.balance).toLocaleString();
    
    const sumVal = Math.floor(state.balance * (state.rates.coin_to_sum || (5000 / 10000))).toLocaleString();
    let ucVal = 0;
    if (state.balance >= 8000 && state.balance < 15000) {
        ucVal = Math.floor(33 + ((state.balance - 8000) / 7000) * 27);
    } else if (state.balance >= 15000) {
        ucVal = Math.floor((state.balance / 15000) * 60);
    } else {
        ucVal = Math.floor((state.balance / 8000) * 33);
    }
    document.getElementById("rate-preview").innerText = `≈ ${sumVal} so'm | ${ucVal} UC`;

    // Energy
    document.getElementById("energy-current").innerText = Math.floor(state.energy).toLocaleString();
    document.getElementById("energy-max").innerText = state.maxEnergy.toLocaleString();
    const energyPercent = Math.max(0, Math.min(100, (state.energy / state.maxEnergy) * 100));
    document.getElementById("energy-bar-fill").style.width = `${energyPercent}%`;

    // Boost Tab
    if (state.upgradeCosts.multitap) {
        document.getElementById("cost-multitap").innerText = `🪙 ${state.upgradeCosts.multitap.toLocaleString()}`;
        document.getElementById("cost-max-energy").innerText = `🪙 ${state.upgradeCosts.max_energy.toLocaleString()}`;
        document.getElementById("cost-regen").innerText = `🪙 ${state.upgradeCosts.regen.toLocaleString()}`;
        document.getElementById("cost-autobot").innerText = `🪙 ${state.upgradeCosts.autobot.toLocaleString()}`;
        
        document.getElementById("multitap-effect").innerText = `+${state.multitap + 1}`;
        document.getElementById("energy-effect").innerText = `+100`;
    }

    // Auto-Bot Claim Banner
    const autoBox = document.getElementById("autobot-claim-box");
    if (state.autobotLevel > 0) {
        autoBox.style.display = "flex";
        document.getElementById("autobot-rate-text").innerText = `Lvl ${state.autobotLevel} (Soatiga ${state.autobotLevel * 50} 🪙)`;
    } else {
        autoBox.style.display = "none";
    }

    // Friends Tab
    document.getElementById("ref-bonus-val").innerText = `+${state.rates.ref_bonus} 🪙`;
    const refLink = `https://t.me/Aurex_Tekin_uc_bot?start=${state.userId}`;
    document.getElementById("ref-link-input").value = refLink;
    document.getElementById("stat-ref-count").innerText = `${state.referralCount} ta`;
    document.getElementById("stat-ref-earned").innerText = `${(state.referralCount * state.rates.ref_bonus).toLocaleString()} 🪙`;

    // Profile Tab
    document.getElementById("prof-name").innerText = state.fullName;
    document.getElementById("prof-id").innerText = `ID: ${state.userId}`;
    document.getElementById("prof-username").innerText = state.username ? `@${state.username}` : "Mavjud emas";
    document.getElementById("prof-total-earned").innerText = `${Math.floor(state.totalEarned).toLocaleString()} 🪙`;
    document.getElementById("prof-balance").innerText = `${Math.floor(state.balance).toLocaleString()} 🪙`;
    document.getElementById("prof-multitap").innerText = `${state.multitap} Lvl (+${state.multitap}/tap)`;
    document.getElementById("prof-max-energy").innerText = `${state.maxEnergy} Max`;
    document.getElementById("prof-autobot").innerText = `${state.autobotLevel} Lvl (${state.autobotLevel * 50} coin/soat)`;
    document.getElementById("prof-date").innerText = state.createdAt || "-";
}

function getRankName(total) {
    if (total > 500000) return "👑 Mythic Ace";
    if (total > 150000) return "💎 Diamond Hero";
    if (total > 50000) return "🔥 Platinum Ace";
    if (total > 15000) return "⚡️ Gold Fighter";
    if (total > 3000) return "🥈 Silver Hunter";
    return "🥉 Bronze Novice";
}

// MODERN SENSOR MULTI-TOUCH & PHYSICS
function setupSensorEventListeners() {
    const wrapper = document.getElementById("clicker-wrapper");
    const disc = document.getElementById("clicker-disc");

    wrapper.addEventListener("touchstart", (e) => {
        e.preventDefault();
        for (let i = 0; i < e.targetTouches.length; i++) {
            const touch = e.targetTouches[i];
            triggerSensorTap(touch.clientX, touch.clientY);
        }
    }, { passive: false });

    wrapper.addEventListener("mousedown", (e) => {
        triggerSensorTap(e.clientX, e.clientY);
    });

    const calculateTilt = (clientX, clientY) => {
        const rect = disc.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const deltaX = clientX - centerX;
        const deltaY = clientY - centerY;
        const rotateX = -(deltaY / (rect.height / 2)) * 18;
        const rotateY = (deltaX / (rect.width / 2)) * 18;
        disc.style.transform = `perspective(600px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(0.95)`;
    };

    wrapper.addEventListener("touchmove", (e) => {
        if (e.targetTouches.length > 0) {
            calculateTilt(e.targetTouches[0].clientX, e.targetTouches[0].clientY);
        }
    });

    const resetDisc = () => {
        disc.style.transform = "perspective(600px) rotateX(0deg) rotateY(0deg) scale(1)";
    };

    wrapper.addEventListener("touchend", resetDisc);
    wrapper.addEventListener("mouseup", resetDisc);
    wrapper.addEventListener("mouseleave", resetDisc);

    document.getElementById("claim-autobot-btn").addEventListener("click", claimAutobot);
}

function triggerSensorTap(clientX, clientY) {
    if (state.energy < state.multitap) {
        showToast("⚡️ Quvvat yetarli emas! Kuting.");
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("warning");
        return;
    }

    const earned = state.multitap;
    state.energy -= earned;
    state.balance += earned;
    state.totalEarned += earned;
    state.pendingTaps += 1;

    if (tg?.HapticFeedback) {
        try { tg.HapticFeedback.impactOccurred("medium"); } catch(e) {}
    }

    playTapSound();
    spawnShockwave(clientX, clientY);
    spawnScoreParticle(clientX, clientY, `+${earned}`);
    spawnSparkBurst(clientX, clientY);

    renderUI();
    debounceSyncTaps();
}

function spawnShockwave(clientX, clientY) {
    const wrapper = document.getElementById("clicker-wrapper");
    const rect = wrapper.getBoundingClientRect();
    const wave = document.createElement("div");
    wave.className = "shockwave";
    wave.style.left = `${clientX - rect.left}px`;
    wave.style.top = `${clientY - rect.top}px`;
    wrapper.appendChild(wave);
    setTimeout(() => wave.remove(), 500);
}

function spawnScoreParticle(clientX, clientY, text) {
    const wrapper = document.getElementById("clicker-wrapper");
    const rect = wrapper.getBoundingClientRect();
    const particle = document.createElement("div");
    particle.className = "floating-particle";
    particle.innerText = text;

    let x = clientX - rect.left;
    let y = clientY - rect.top;

    x = Math.max(30, Math.min(rect.width - 30, x));
    y = Math.max(30, Math.min(rect.height - 30, y));

    particle.style.left = `${x}px`;
    particle.style.top = `${y}px`;

    wrapper.appendChild(particle);
    setTimeout(() => particle.remove(), 850);
}

function spawnSparkBurst(clientX, clientY) {
    const wrapper = document.getElementById("clicker-wrapper");
    const rect = wrapper.getBoundingClientRect();
    const count = 5;

    for (let i = 0; i < count; i++) {
        const spark = document.createElement("div");
        spark.className = "spark";
        const angle = (Math.PI * 2 / count) * i + (Math.random() * 0.5);
        const distance = 40 + Math.random() * 40;
        const dx = Math.cos(angle) * distance;
        const dy = Math.sin(angle) * distance;

        spark.style.setProperty("--dx", `${dx}px`);
        spark.style.setProperty("--dy", `${dy}px`);
        spark.style.left = `${clientX - rect.left}px`;
        spark.style.top = `${clientY - rect.top}px`;

        wrapper.appendChild(spark);
        setTimeout(() => spark.remove(), 600);
    }
}

// Debounced backend sync
let syncTimer = null;
function debounceSyncTaps() {
    clearTimeout(syncTimer);
    syncTimer = setTimeout(async () => {
        if (state.pendingTaps <= 0) return;
        
        const count = state.pendingTaps;
        state.pendingTaps = 0;

        try {
            const res = await fetch("/api/tap", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: state.userId, count: count })
            });
            const data = await res.json();
            if (data.user) {
                updateLocalState(data.user);
                renderUI();
            }
        } catch (e) {
            console.error("Tap sync error:", e);
        }
    }, 400);
}

function startClientEnergyRegen() {
    setInterval(() => {
        if (state.energy < state.maxEnergy) {
            const regenFactor = 1 + (state.regenLevel - 1) * 0.25;
            const energyPerSecond = (state.maxEnergy / 3600) * regenFactor;
            state.energy = Math.min(state.maxEnergy, state.energy + energyPerSecond);
            
            document.getElementById("energy-current").innerText = Math.floor(state.energy);
            const energyPercent = Math.max(0, Math.min(100, (state.energy / state.maxEnergy) * 100));
            document.getElementById("energy-bar-fill").style.width = `${energyPercent}%`;
        }
    }, 1000);
}

// UPGRADES
async function buyUpgrade(type) {
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("heavy");

    try {
        const res = await fetch("/api/upgrade", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: state.userId, type: type })
        });
        const data = await res.json();
        
        showToast(data.message);
        if (data.user) {
            updateLocalState(data.user, data.upgradeCosts);
            renderUI();
        }
    } catch (e) {
        showToast("Xatolik yuz berdi!");
    }
}

// AUTOBOT
async function claimAutobot() {
    if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");

    try {
        const res = await fetch("/api/claim_autobot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: state.userId })
        });
        const data = await res.json();
        
        showToast(data.message);
        if (data.user) {
            updateLocalState(data.user);
            renderUI();
        }
    } catch (e) {
        showToast("Xatolik yuz berdi!");
    }
}

// TAB NAVIGATION
function switchTab(tabId) {
    if (tg?.HapticFeedback) tg.HapticFeedback.selectionChanged();
    if (tabId === "admin" && !state.isAdmin && state.userId !== 8825408278) {
        showToast("Sizda Admin huquqi yo'q!");
        return;
    }

    document.querySelectorAll(".tab-pane").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".nav-btn").forEach(el => el.classList.remove("active"));

    const targetTab = document.getElementById(`tab-${tabId}`);
    if (targetTab) targetTab.classList.add("active");

    const navButtons = document.querySelectorAll(".nav-btn");
    const tabs = ["clicker", "boost", "withdraw", "friends", "profile", "admin"];
    const idx = tabs.indexOf(tabId);
    if (idx !== -1 && navButtons[idx]) {
        navButtons[idx].classList.add("active");
    }

    renderUI();
    if (tabId === "admin" || state.isAdmin) {
        loadAdminData();
    }
}

// WITHDRAWAL
function switchWithdrawType(type) {
    state.currentWithdrawType = type;
    document.getElementById("sw-card").classList.toggle("active", type === "CARD");
    document.getElementById("sw-pubg").classList.toggle("active", type === "PUBG");

    document.getElementById("fields-card").style.display = type === "CARD" ? "block" : "none";
    document.getElementById("fields-pubg").style.display = type === "PUBG" ? "block" : "none";

    calculateWithdrawPreview();
}

function calculateWithdrawPreview() {
    const inputVal = parseFloat(document.getElementById("w-amount").value) || 0;
    const calcBox = document.getElementById("calc-preview");

    if (state.currentWithdrawType === "CARD") {
        const sum = Math.floor(inputVal * (state.rates.coin_to_sum || (5000 / 10000)));
        calcBox.innerHTML = `Olasiz: <b>${sum.toLocaleString()} so'm</b> (Min: ${(state.rates.min_card || 10000).toLocaleString()} 🪙 = 5,000 so'm)`;
    } else {
        let uc = 0;
        if (inputVal >= 8000 && inputVal < 15000) {
            uc = Math.floor(33 + ((inputVal - 8000) / 7000) * 27);
        } else if (inputVal >= 15000) {
            uc = Math.floor((inputVal / 15000) * 60);
        }
        calcBox.innerHTML = `Olasiz: <b>${uc.toLocaleString()} UC</b> (Min: ${(state.rates.min_pubg || 8000).toLocaleString()} 🪙 = 33 UC | 15,000 🪙 = 60 UC)`;
    }
}

async function submitWithdrawal() {
    const amount = parseFloat(document.getElementById("w-amount").value);
    if (!amount || amount <= 0) {
        showToast("Iltimos, tangalar miqdorini to'g'ri kiriting!");
        return;
    }

    if (amount > state.balance) {
        showToast("Balansingizda yetarli tanga yo'q!");
        return;
    }

    let targetVal = "";
    let targetDetails = "";

    if (state.currentWithdrawType === "CARD") {
        if (amount < state.rates.min_card) {
            showToast(`Minimal yechish: ${state.rates.min_card} coin!`);
            return;
        }
        targetVal = document.getElementById("w-card-num").value.trim();
        targetDetails = document.getElementById("w-card-holder").value.trim();
        if (targetVal.length < 16) {
            showToast("Karta raqami 16 ta raqam bo'lishi kerak!");
            return;
        }
        if (!targetDetails) {
            showToast("Karta egasining ismini kiriting!");
            return;
        }
    } else {
        if (amount < state.rates.min_pubg) {
            showToast(`Minimal yechish: ${state.rates.min_pubg} coin!`);
            return;
        }
        targetVal = document.getElementById("w-pubg-id").value.trim();
        targetDetails = document.getElementById("w-pubg-nick").value.trim();
        if (!targetVal) {
            showToast("PUBG Player ID ni kiriting!");
            return;
        }
        if (!targetDetails) {
            showToast("PUBG Nickname ni kiriting!");
            return;
        }
    }

    const btn = document.getElementById("submit-withdraw-btn");
    btn.disabled = true;
    btn.innerText = "YUBORILMOQDA...";

    try {
        const res = await fetch("/api/withdraw", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: state.userId,
                type: state.currentWithdrawType,
                amount_coins: amount,
                target_val: targetVal,
                target_details: targetDetails
            })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message);
            if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
            document.getElementById("w-amount").value = "";
            document.getElementById("w-card-num").value = "";
            document.getElementById("w-card-holder").value = "";
            document.getElementById("w-pubg-id").value = "";
            document.getElementById("w-pubg-nick").value = "";
            if (data.user) updateLocalState(data.user);
            renderUI();
        } else {
            showToast(data.error || "Xatolik yuz berdi!");
        }
    } catch (e) {
        showToast("Tarmoq xatosi!");
    } finally {
        btn.disabled = false;
        btn.innerText = "YECHIB OLISH SO'ROVINI YUBORISH";
    }
}

function copyRefLink() {
    const input = document.getElementById("ref-link-input");
    input.select();
    navigator.clipboard.writeText(input.value);
    showToast("Taklif havolasi nusxalandi! 📋");
    if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
}

function shareToTelegram() {
    const link = document.getElementById("ref-link-input").value;
    const text = encodeURIComponent("🐹 Aurex PUBG Cyber Clicker ga qo'shiling va bepul PUBG UC hamda naqd pul ishlang! 🔥\n\n" + link);
    if (tg) {
        tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${text}`);
    } else {
        window.open(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${text}`, "_blank");
    }
}

// ==================== WEB APP ADMIN LOGIC ====================

function switchAdminSubTab(subId) {
    if (tg?.HapticFeedback) tg.HapticFeedback.selectionChanged();

    document.querySelectorAll(".adm-sub-pane").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".adm-tab-btn").forEach(el => el.classList.remove("active"));

    const target = document.getElementById(`adm-sub-${subId}`);
    if (target) target.classList.add("active");

    const btns = document.querySelectorAll(".adm-tab-btn");
    const tabs = ["stats", "withdrawals", "users", "settings", "channels", "broadcast"];
    const idx = tabs.indexOf(subId);
    if (idx !== -1 && btns[idx]) {
        btns[idx].classList.add("active");
    }
}

async function loadAdminData() {
    try {
        const adminId = state.userId || 8825408278;
        const res = await fetch(`/api/admin/data?admin_id=${adminId}`);
        const data = await res.json();

        if (data.stats) {
            document.getElementById("adm-total-users").innerText = `${data.stats.total_users} ta`;
            document.getElementById("adm-banned-users").innerText = `${data.stats.banned_users} ta`;
            document.getElementById("adm-pending-w").innerText = `${data.stats.pending_withdrawals} ta`;
            document.getElementById("adm-total-coins").innerText = `${Math.floor(data.stats.total_balance).toLocaleString()} 🪙`;
            document.getElementById("adm-paid-sum").innerText = `${(data.stats.approved_card_sum || 0).toLocaleString()} so'm`;
            document.getElementById("adm-paid-uc").innerText = `${(data.stats.approved_pubg_uc || 0).toLocaleString()} UC`;
        }

        // Render Withdrawals
        const wContainer = document.getElementById("adm-withdrawals-list");
        if (data.withdrawals && data.withdrawals.length > 0) {
            wContainer.innerHTML = "";
            data.withdrawals.forEach(w => {
                const unit = w.type === "CARD" ? "so'm" : "UC";
                const card = document.createElement("div");
                card.className = "adm-item-card";
                card.innerHTML = `
                    <div class="adm-card-header">
                        <span>#${w.id} (${w.type})</span>
                        <span style="color:#ffaa00;">${w.amount_target.toLocaleString()} ${unit} (${w.amount_coins} 🪙)</span>
                    </div>
                    <div class="adm-card-row"><span>User ID:</span> <b>${w.user_id}</b></div>
                    <div class="adm-card-row"><span>Rekvizit:</span> <b>${w.target_value}</b></div>
                    <div class="adm-card-row"><span>Tafsilot:</span> <b>${w.target_details}</b></div>
                    <div class="adm-card-row"><span>Sana:</span> <b>${w.created_at}</b></div>
                    <div class="adm-actions-row">
                        <button class="adm-btn-approve" onclick="adminResolveW(${w.id}, 'APPROVED')">✅ TO'LANDI</button>
                        <button class="adm-btn-reject" onclick="adminResolveW(${w.id}, 'REJECTED')">❌ RAD ETISH</button>
                    </div>
                `;
                wContainer.appendChild(card);
            });
        } else {
            wContainer.innerHTML = `<div class="empty-hint">✅ Kutilayotgan zayafkalar yo'q.</div>`;
        }

        // Prefill settings
        if (data.settings) {
            document.getElementById("set-rate-sum").value = data.settings.coin_to_sum_rate || 5000;
            document.getElementById("set-rate-uc").value = data.settings.coin_to_uc_rate || 60;
            document.getElementById("set-min-card").value = data.settings.card_min_withdraw || 10000;
            document.getElementById("set-min-pubg").value = data.settings.pubg_min_withdraw || 8000;
            document.getElementById("set-init-limit").value = data.settings.initial_max_energy || 200;
            document.getElementById("set-ref-bonus").value = data.settings.referral_bonus || 50;
            document.getElementById("set-zayafka-ch").value = data.settings.zayafka_channel_id || "";
        }

        // Render Channels
        const chContainer = document.getElementById("adm-channels-list");
        if (data.channels && data.channels.length > 0) {
            chContainer.innerHTML = "";
            data.channels.forEach(ch => {
                const div = document.createElement("div");
                div.className = "adm-item-card";
                div.innerHTML = `
                    <div class="adm-card-header">
                        <span>📢 ${ch.channel_title}</span>
                        <button class="adm-btn-reject" style="max-width:80px; padding:4px;" onclick="adminDeleteChannel('${ch.channel_id}')">O'chirish</button>
                    </div>
                    <div class="adm-card-row"><span>ID:</span> <b>${ch.channel_id}</b></div>
                    <div class="adm-card-row"><span>Link:</span> <b>${ch.channel_url}</b></div>
                `;
                chContainer.appendChild(div);
            });
        } else {
            chContainer.innerHTML = `<div class="empty-hint">Majburiy kanallar ulanmagan.</div>`;
        }
    } catch (e) {
        console.error("Admin data error:", e);
    }
}

async function adminResolveW(wId, status) {
    let note = "";
    if (status === "REJECTED") {
        note = prompt("Rad etish sababini yozing (Userga yuboriladi):", "Noto'g'ri rekvizit");
        if (note === null) return;
    }

    try {
        const res = await fetch("/api/admin/resolve_withdrawal", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                admin_id: state.userId || 8825408278,
                withdrawal_id: wId,
                status: status,
                note: note
            })
        });
        const data = await res.json();
        showToast(data.message || "Bajarildi!");
        loadAdminData();
    } catch (e) {
        showToast("Xatolik!");
    }
}

async function adminSearchUser() {
    const q = document.getElementById("adm-user-search-input").value.trim();
    if (!q) {
        showToast("Qidiruv uchun ID yoki username yozing!");
        return;
    }

    try {
        const res = await fetch("/api/admin/search_user", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ admin_id: state.userId || 8825408278, query: q })
        });
        const data = await res.json();
        const resultsBox = document.getElementById("adm-users-results") || document.getElementById("adm-user-search-result");

        if (data.users && data.users.length > 0) {
            resultsBox.innerHTML = "";
            data.users.forEach(u => {
                const card = document.createElement("div");
                card.className = "adm-item-card";
                const isBanned = Boolean(u.is_banned);
                card.innerHTML = `
                    <div class="adm-card-header">
                        <span>👤 ${u.full_name}</span>
                        <span style="color:${isBanned ? '#ff1744' : '#00e676'};">${isBanned ? '🔴 BLOKLANGAN' : '🟢 FAOL'}</span>
                    </div>
                    <div class="adm-card-row"><span>ID:</span> <b>${u.user_id}</b></div>
                    <div class="adm-card-row"><span>Username:</span> <b>@${u.username || 'yoq'}</b></div>
                    <div class="adm-card-row"><span>Balans:</span> <b>${u.balance.toLocaleString()} 🪙</b></div>
                    <div class="adm-card-row"><span>Jami ishlangan:</span> <b>${u.total_earned.toLocaleString()} 🪙</b></div>
                    <div class="adm-card-row"><span>Quvvat:</span> <b>${u.energy}/${u.max_energy}</b></div>
                    <div class="adm-card-row"><span>Multitap:</span> <b>${u.multitap_level} Lvl</b></div>
                    <div class="adm-card-row"><span>Referallar:</span> <b>${u.referral_count} ta</b></div>
                    <div class="adm-actions-row">
                        <button class="adm-btn-approve" onclick="adminAdjustBal(${u.user_id}, 'ADD')">➕ QO'SHISH</button>
                        <button class="adm-btn-reject" onclick="adminAdjustBal(${u.user_id}, 'SUB')">➖ AYIRISH</button>
                    </div>
                    <div class="adm-actions-row">
                        <button class="cyber-btn" style="flex:1;" onclick="adminSendDirectMsg(${u.user_id})">✍️ LICHKAGA YOZISH</button>
                        <button class="${isBanned ? 'adm-btn-approve' : 'adm-btn-reject'}" style="flex:1;" onclick="adminToggleBanAction(${u.user_id}, ${!isBanned})">
                            ${isBanned ? '🟢 BANDAN OLISH' : '🔴 BLOKLASH'}
                        </button>
                    </div>
                `;
                resultsBox.appendChild(card);
            });
        } else {
            resultsBox.innerHTML = `<div class="empty-hint">Foydalanuvchi topilmadi!</div>`;
        }
    } catch (e) {
        showToast("Qidiruvda xatolik!");
    }
}

async function adminAdjustBal(uid, mode) {
    const val = prompt(`Foydalanuvchiga (${uid}) qancha tanga ${mode === 'ADD' ? "qo'shilsin" : "ayirilsin"}?`, "100");
    if (!val || isNaN(val)) return;

    try {
        const res = await fetch("/api/admin/update_balance", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                admin_id: state.userId,
                target_user_id: uid,
                amount: parseFloat(val),
                mode: mode
            })
        });
        const data = await res.json();
        showToast(data.message || "Balans yangilandi!");
        adminSearchUser();
    } catch (e) {
        showToast("Xatolik!");
    }
}

async function adminToggleBanAction(uid, shouldBan) {
    let reason = "Admin tomonidan bloklandi";
    if (shouldBan) {
        const inputReason = prompt("Bloklash sababini yozing:", "Qoidabuzarlik");
        if (inputReason === null) return;
        if (inputReason) reason = inputReason;
    }

    try {
        const res = await fetch("/api/admin/toggle_ban", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                admin_id: state.userId || 8825408278,
                target_user_id: uid,
                is_ban: shouldBan,
                reason: reason
            })
        });
        const data = await res.json();
        showToast(shouldBan ? "Foydalanuvchi bloklandi!" : "Bandan chiqarildi!");
        adminSearchUser();
    } catch (e) {
        showToast("Xatolik!");
    }
}

async function adminSendDirectMsg(uid) {
    const text = prompt(`Foydalanuvchiga (${uid}) yubormoqchi bo'lgan xabaringizni yozing:`);
    if (!text) return;

    try {
        const res = await fetch("/api/admin/send_message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                admin_id: state.userId || 8825408278,
                target_user_id: uid,
                text: text
            })
        });
        const data = await res.json();
        showToast(data.message || (data.success ? "Xabar yuborildi!" : data.error));
    } catch (e) {
        showToast("Xatolik!");
    }
}

async function adminSaveSettings() {
    const settings = {
        coin_to_sum_rate: document.getElementById("set-rate-sum").value,
        coin_to_uc_rate: document.getElementById("set-rate-uc").value,
        card_min_withdraw: document.getElementById("set-min-card").value,
        pubg_min_withdraw: document.getElementById("set-min-pubg").value,
        initial_max_energy: document.getElementById("set-init-limit").value,
        referral_bonus: document.getElementById("set-ref-bonus").value,
        zayafka_channel_id: document.getElementById("set-zayafka-ch").value
    };

    try {
        const res = await fetch("/api/admin/update_settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ admin_id: state.userId || 8825408278, settings: settings })
        });
        const data = await res.json();
        showToast(data.message || "Sozlamalar saqlandi!");
    } catch (e) {
        showToast("Xatolik!");
    }
}

async function adminAddChannel() {
    const cidEl = document.getElementById("adm-add-channel-id") || document.getElementById("add-ch-id");
    const titleEl = document.getElementById("adm-add-channel-title") || document.getElementById("add-ch-title");
    const urlEl = document.getElementById("adm-add-channel-url") || document.getElementById("add-ch-url");

    const cid = cidEl ? cidEl.value.trim() : "";
    const title = titleEl ? titleEl.value.trim() : "";
    const url = urlEl ? urlEl.value.trim() : "";

    if (!cid || !title || !url) {
        showToast("Barcha maydonlarni to'ldiring!");
        return;
    }

    try {
        const res = await fetch("/api/admin/channels", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                admin_id: state.userId || 8825408278,
                action: "add",
                channel_id: cid,
                channel_title: title,
                channel_url: url
            })
        });
        const data = await res.json();
        showToast(data.message || "Kanal qo'shildi!");
        if (cidEl) cidEl.value = "";
        if (titleEl) titleEl.value = "";
        if (urlEl) urlEl.value = "";
        loadAdminData();
    } catch (e) {
        showToast("Xatolik!");
    }
}

async function adminDeleteChannel(cid) {
    if (!confirm(`Haqiqatan ham ushbu kanalni o'chirmoqchimisiz? (${cid})`)) return;

    try {
        const res = await fetch("/api/admin/channels", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                admin_id: state.userId || 8825408278,
                action: "delete",
                channel_id: cid
            })
        });
        const data = await res.json();
        showToast("Kanal o'chirildi!");
        loadAdminData();
    } catch (e) {
        showToast("Xatolik!");
    }
}

async function adminSendBroadcast() {
    const text = document.getElementById("adm-broadcast-text").value.trim();
    if (!text) {
        showToast("Xabar matnini kiriting!");
        return;
    }

    if (!confirm("Barcha faol foydalanuvchilarga ushbu xabarni tarqatishni tasdiqlaysizmi?")) return;

    const btn = document.getElementById("adm-broadcast-btn");
    btn.disabled = true;
    btn.innerText = "YUBORILMOQDA...";

    try {
        const res = await fetch("/api/admin/broadcast", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ admin_id: state.userId || 8825408278, text: text })
        });
        const data = await res.json();
        showToast(data.message || "Xabar tarqatildi!");
        document.getElementById("adm-broadcast-text").value = "";
    } catch (e) {
        showToast("Xatolik!");
    } finally {
        btn.disabled = false;
        btn.innerText = "BARCHAGA YUBORISH (REKLAMA)";
    }
}

let toastTimeout;
function showToast(message) {
    const toast = document.getElementById("toast");
    toast.innerText = message;
    toast.classList.add("show");
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toast.classList.remove("show");
    }, 2800);
}
