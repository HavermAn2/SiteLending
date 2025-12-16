let available = {}; // { '2025-12-18': ['09:00', '12:00'], ... }
let fp = null;

const timeSelect = document.getElementById("customers-time");

async function loadBookings() {
  const res = await fetch("http://127.0.0.1:8000/bookings");
  const data = await res.json();
  console.log(data); // для проверки

  // берем то, что вернул бэк
  available = data.dates_times || {};

  // список доступных дат = ключи объекта
  const enabledDates = Object.keys(available); // ["2025-12-18", "2025-12-19"]

  if (!fp) {
    fp = flatpickr("#customers-date", {
      dateFormat: "Y-m-d",
      enable: enabledDates, // РАЗРЕШАЕМ только эти даты
      onChange: function (selectedDates, dateStr) {
        updateTimeOptions(dateStr);
      },
    });
  } else {
    // если данные обновились, можно обновить enable
    fp.set("enable", enabledDates);
  }
}

function updateTimeOptions(dateStr) {
  timeSelect.innerHTML = "";

  const times = available[dateStr] || [];

  if (times.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Нет доступного времени";
    timeSelect.appendChild(opt);
    timeSelect.disabled = true;
    return;
  }

  timeSelect.disabled = false;

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Выберите время";
  placeholder.disabled = true;
  placeholder.selected = true;
  timeSelect.appendChild(placeholder);

  times.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    timeSelect.appendChild(opt);
  });
}

loadBookings();
setInterval(loadBookings, 20000);
