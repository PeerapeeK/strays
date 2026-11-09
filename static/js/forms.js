(function () {
    'use strict';

    var ALLOWED_TYPES = ['image/jpeg', 'image/png'];
    var ALLOWED_EXTENSION = /\.(jpe?g|png)$/i;
    var MAX_SIZE = 5 * 1024 * 1024;

    function setupLoadingState() {
        document.querySelectorAll('form[data-loading-form]').forEach(function (form) {
            form.addEventListener('submit', function () {
                if (form.dataset.submitting === '1') {
                    return;
                }
                form.dataset.submitting = '1';
                form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (button) {
                    button.disabled = true;
                    button.classList.add('is-loading');
                    var text = button.dataset.loadingText || 'กำลังบันทึก...';
                    if (button.tagName === 'INPUT') {
                        button.value = text;
                    } else {
                        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>' + text;
                    }
                });
            });
        });
    }

    function setupPhotoPreviews() {
        document.querySelectorAll('input[type="file"][data-photo-preview]').forEach(function (input) {
            var preview = document.getElementById(input.dataset.photoPreview);
            var errorBox = input.dataset.photoError ? document.getElementById(input.dataset.photoError) : null;
            var objectUrls = [];

            function revokeUrls() {
                objectUrls.forEach(function (url) { URL.revokeObjectURL(url); });
                objectUrls = [];
            }

            function showError(message) {
                if (!errorBox) {
                    return;
                }
                errorBox.textContent = message || '';
                errorBox.classList.toggle('d-none', !message);
            }

            input.addEventListener('change', function () {
                revokeUrls();
                showError('');
                if (preview) {
                    preview.innerHTML = '';
                }

                var files = Array.prototype.slice.call(input.files || []);
                if (!files.length) {
                    return;
                }

                var invalid = files.find(function (file) {
                    return ALLOWED_TYPES.indexOf(file.type) === -1 && !ALLOWED_EXTENSION.test(file.name);
                });
                if (invalid) {
                    showError('ไฟล์ "' + invalid.name + '" ไม่ใช่รูปแบบที่รองรับ (รับเฉพาะ JPG, JPEG หรือ PNG)');
                    input.value = '';
                    return;
                }

                var tooLarge = files.find(function (file) {
                    return file.size > MAX_SIZE;
                });
                if (tooLarge) {
                    showError('ไฟล์ "' + tooLarge.name + '" มีขนาดเกิน 5 MB');
                    input.value = '';
                    return;
                }

                if (!preview) {
                    return;
                }

                files.forEach(function (file) {
                    var url = URL.createObjectURL(file);
                    objectUrls.push(url);

                    var figure = document.createElement('figure');
                    figure.className = 'photo-preview-item';

                    var image = document.createElement('img');
                    image.src = url;
                    image.alt = file.name;

                    var caption = document.createElement('figcaption');
                    caption.textContent = file.name;

                    figure.appendChild(image);
                    figure.appendChild(caption);
                    preview.appendChild(figure);
                });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        setupLoadingState();
        setupPhotoPreviews();
    });
})();
