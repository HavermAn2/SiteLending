let disabledDates = [];
let fp = null;

async function loadBookings() {
  const res = await fetch("http://127.0.0.1:8000/bookings");
  const data = await res.json();

  console.log("raw data =", data);
  console.log("data.dates =", data.dates);

  const dates = Array.isArray(data.dates) ? data.dates : [];
  disabledDates = dates;

  if (!fp) {
    fp = flatpickr("#customers-date", {
      dateFormat: "Y-m-d",
      disable: disabledDates,
    });
  } else {
    fp.set("disable", disabledDates);
  }
}

loadBookings();
setInterval(loadBookings, 20000);
