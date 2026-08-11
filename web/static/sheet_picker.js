(function (global) {
  'use strict';

  function normalized(value) {
    return String(value || '').normalize('NFKC').trim().toLocaleLowerCase();
  }

  global.createSheetPickerSearch = function createSheetPickerSearch(options) {
    const rows = () => [...options.list.querySelectorAll('.sheet-row')];

    const refresh = (resetQuery = false) => {
      if (resetQuery) options.input.value = '';
      const query = normalized(options.input.value);
      let visible = 0;
      const allRows = rows();

      allRows.forEach(row => {
        const matched = !query ||
          normalized(row.dataset.sheetName).includes(query);
        row.hidden = !matched;
        if (matched) visible += 1;
      });

      options.count.textContent = `${visible} / ${allRows.length} Sheet`;
      options.empty.hidden = visible !== 0;
    };

    const setVisible = checked => {
      rows().filter(row => !row.hidden).forEach(row => {
        const box = row.querySelector('input[type="checkbox"]');
        if (box) box.checked = checked;
      });
    };

    options.input.addEventListener('input', () => refresh(false));
    options.selectAllButton.addEventListener('click', () => setVisible(true));
    options.clearButton.addEventListener('click', () => setVisible(false));
    return {refresh};
  };
})(window);
