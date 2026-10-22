'use strict';
(() => {
  const normalize = value => String(value).replace(/[۰-۹٠-٩]/g, digit => {
    const code = digit.charCodeAt(0);
    return String(code >= 1776 ? code - 1776 : code - 1632);
  });
  const data = document.getElementById('resource-options');
  const subject = document.getElementById('id_subject');
  const resource = document.getElementById('id_resource');
  if (data && subject && resource) {
    const options = JSON.parse(data.textContent);
    const update = () => {
      const selected = resource.value;
      resource.replaceChildren(new Option('منبع را انتخاب کنید', ''));
      options.filter(item => String(item.subject) === subject.value).forEach(item => {
        resource.add(new Option(item.title, String(item.id)));
      });
      if ([...resource.options].some(option => option.value === selected)) resource.value = selected;
    };
    subject.addEventListener('change', update);
    update();
  }
  const total = document.getElementById('practice-total');
  if (total) {
    const fields = ['correct_count', 'wrong_count', 'unanswered_count'].map(name => document.getElementById(`id_${name}`));
    const update = () => {
      const sum = fields.reduce((sum, input) => sum + Math.max(0, Number(normalize(input.value)) || 0), 0);
      total.textContent = `مجموع تست: ${sum.toLocaleString('fa-IR')}`;
    };
    fields.forEach(input => input.addEventListener('input', update));
    update();
  }
})();
