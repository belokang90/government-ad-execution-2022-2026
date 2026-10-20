"use strict";
document.addEventListener("DOMContentLoaded", async () => {
  const list = document.getElementById("publishedList");
  try {
    const response = await fetch("/api/articles/published");
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || "기사를 불러오지 못했습니다.");
    list.replaceChildren();
    if (!data.articles.length) {
      list.textContent = "아직 승인된 기사가 없습니다.";
      return;
    }
    for (const article of data.articles) {
      const card = document.createElement("article");
      card.className = "card published-card";
      const title = document.createElement("h2");
      title.textContent = article.title;
      const note = document.createElement("p");
      note.className = "muted";
      note.textContent = `${article.base_year}년 기준 → ${article.current_year}년 비교`;
      const body = document.createElement("div");
      body.className = "published-body";
      body.textContent = article.body;
      card.append(note, title, body);
      list.append(card);
    }
  } catch (e) {
    list.textContent = e.message;
    list.classList.add("error");
  }
});
