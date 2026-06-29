let DATA = { roles: [] };

const $ = (sel) => document.querySelector(sel);
const meta = $("#meta");
const rolesPanel = $("#rolesPanel");
const detailsPanel = $("#detailsPanel");
const petsPanel = $("#petsPanel");

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function getFilters() {
  return {
    q: $("#q").value.trim().toLowerCase(),
    type: $("#type").value,
    priceMin: $("#priceMin").value ? Number($("#priceMin").value) : null,
    priceMax: $("#priceMax").value ? Number($("#priceMax").value) : null,
  };
}

function matchRole(role, f) {
  if (f.priceMin != null && (role.price ?? 0) < f.priceMin) return false;
  if (f.priceMax != null && (role.price ?? 0) > f.priceMax) return false;
  if (!f.q) return true;
  const parts = [role.role_name, role.school, role.ordersn, role.server_name, role.desc_sumup];
  (role.summons || []).forEach((s) => parts.push(s.name, s.skills, s.pet_score));
  (role.equips || []).forEach((e) => parts.push(e.name, e.type, e.props));
  return parts.join(" ").toLowerCase().includes(f.q);
}

function filterRoles() {
  return DATA.roles.filter((r) => matchRole(r, getFilters()));
}

function flattenDetails(roles, typeFilter) {
  const rows = [];
  for (const role of roles) {
    for (const eq of role.equips || []) {
      if (typeFilter && eq.type !== typeFilter) continue;
      rows.push({
        role_name: role.role_name,
        price: role.price,
        明细类型: eq.type,
        名称: eq.name,
        数量: eq.amount,
        属性: eq.props,
        特效: eq.special,
        宠物评分: "",
        召唤等级: eq.level,
        速度: "",
        技能: "",
        参战: eq.wearing ? "穿戴" : "",
      });
    }
    for (const pet of role.summons || []) {
      if (typeFilter && pet.type !== typeFilter) continue;
      rows.push({
        role_name: role.role_name,
        price: role.price,
        明细类型: pet.type,
        名称: pet.name,
        数量: "",
        属性: "",
        特效: "",
        宠物评分: pet.pet_score,
        召唤等级: pet.level,
        速度: pet.speed,
        技能: pet.skills,
        参战: pet.fighting,
      });
    }
  }
  return rows;
}

function renderRoles(roles) {
  if (!roles.length) {
    rolesPanel.innerHTML = '<div class="empty">无匹配角色</div>';
    return;
  }
  rolesPanel.innerHTML = `<div class="role-grid">${roles.map((r) => `
    <article class="role-card">
      <h3>${esc(r.role_name)} · ${esc(r.school)} Lv${esc(r.level)}</h3>
      <div class="price">¥${esc(r.price)}</div>
      <div class="sub">${esc(r.server_name)} · ${esc(r.desc_sumup)}</div>
      <div class="sub">人物${esc(r["人物评分"])} / 装备${esc(r["装备评分"])} / 召唤${esc(r["召唤灵评分"])}</div>
      <div class="sub">召唤灵 ${(r.summons || []).length} 只 · 明细 ${(r.equips || []).length + (r.summons || []).length} 条</div>
      <div class="sub">${esc(r.ordersn)}</div>
    </article>
  `).join("")}</div>`;
}

function renderTable(panel, rows, columns) {
  if (!rows.length) {
    panel.innerHTML = '<div class="empty">无匹配数据</div>';
    return;
  }
  panel.innerHTML = `<table>
    <thead><tr>${columns.map((c) => `<th>${esc(c.label)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((row) => `<tr>${columns.map((c) => `<td>${esc(row[c.key])}</td>`).join("")}</tr>`).join("")}</tbody>
  </table>`;
}

function render() {
  const roles = filterRoles();
  const f = getFilters();
  const details = flattenDetails(roles, f.type || null);
  const pets = flattenDetails(roles, null).filter((d) =>
    d["明细类型"] === "召唤灵" || d["明细类型"] === "仓库召唤灵" || d["明细类型"] === "子女"
  );

  renderRoles(roles);
  renderTable(detailsPanel, details, [
    { key: "role_name", label: "角色" },
    { key: "price", label: "价格" },
    { key: "明细类型", label: "类型" },
    { key: "名称", label: "名称" },
    { key: "数量", label: "数量" },
    { key: "属性", label: "属性" },
    { key: "宠物评分", label: "宠物评分" },
    { key: "召唤等级", label: "等级" },
    { key: "速度", label: "速度" },
    { key: "技能", label: "技能" },
    { key: "参战", label: "参战" },
  ]);
  renderTable(petsPanel, pets, [
    { key: "role_name", label: "角色" },
    { key: "price", label: "价格" },
    { key: "名称", label: "召唤灵" },
    { key: "宠物评分", label: "评分" },
    { key: "召唤等级", label: "等级" },
    { key: "速度", label: "速度" },
    { key: "技能", label: "技能" },
    { key: "参战", label: "参战" },
  ]);
}

async function loadData() {
  const cfg = window.MHCBG_CONFIG || {};
  if (!cfg.apiUrl) {
    meta.textContent = "未配置 JSONBin，请先运行 upload_jsonbin.py";
    return;
  }
  const resp = await fetch(cfg.apiUrl);
  if (!resp.ok) throw new Error(`加载失败: ${resp.status}`);
  const json = await resp.json();
  const record = json.record || json;
  DATA.roles = record.roles || [];
  meta.textContent = `共 ${record.total_roles || DATA.roles.length} 个角色 · 更新于 ${record.updated_at || "-"}`;
  render();
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`${btn.dataset.tab}Panel`).classList.add("active");
  });
});

$("#searchBtn").addEventListener("click", render);
["q", "type", "priceMin", "priceMax"].forEach((id) => {
  $(`#${id}`).addEventListener("keydown", (e) => {
    if (e.key === "Enter") render();
  });
});

loadData().catch((err) => {
  meta.textContent = err.message;
});
