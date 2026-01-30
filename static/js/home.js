// глобальные переменные
let selectedVkGroups = [];
let selectedTgChannels = [];
let scheduledTime = null;

// функции
function closeModal(modal) {
    modal.classList.remove('active');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 400);
}

// получение CSRF токена
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// загрузка сохраненных групп
async function loadSavedGroups() {
    try {
        const response = await fetch('/api/get-saved-groups/');
        const data = await response.json();

        if (data.success) {
            renderVkGroups(data.vk_groups);
            renderTgChannels(data.tg_channels);
        }
    } catch (error) {
        console.error('Error loading groups:', error);
    }
}

// загрузка недавних постов
async function loadRecentPosts() {
    try {
        const response = await fetch('/api/get-recent-posts/');
        const data = await response.json();

        if (data.success) {
            renderRecentPosts(data.posts);
        }
    } catch (error) {
        console.error('Error loading recent posts:', error);
    }
}

// отрисовка недавних постов
function renderRecentPosts(posts) {
    const container = document.getElementById('recentPostsList');

    if (!container) return;

    if (posts.length === 0) {
        container.innerHTML = '<div class="no-posts">NO RECENT POSTS</div>';
        return;
    }

    container.innerHTML = posts.map(post => {
        const statusClass = post.status === 'scheduled' ? 'scheduled' : 'published';
        const statusText = post.status === 'scheduled' ? 'SCHEDULED' : 'PUBLISHED';
        const platforms = [];

        if (post.vk_groups && post.vk_groups.length > 0) {
            platforms.push(`VK (${post.vk_groups.length})`);
        }
        if (post.tg_channels && post.tg_channels.length > 0) {
            platforms.push(`TG (${post.tg_channels.length})`);
        }

        const time = post.scheduled_time ?
            new Date(post.scheduled_time).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) :
            new Date(post.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

        return `
            <div class="recent-post ${statusClass}">
                <div class="post-header">
                    <span class="post-status">${statusText}</span>
                    <span class="post-time">${time}</span>
                </div>
                <div class="post-text">${post.text}</div>
                <div class="post-platforms">${platforms.join(' • ')}</div>
            </div>
        `;
    }).join('');
}

// отрисовка vk групп
function renderVkGroups(groups) {
    const container = document.getElementById('vkGroupsList');

    if (!container) return;

    if (groups.length === 0) {
        container.innerHTML = '<div class="no-groups">NO GROUPS SAVED</div>';
        return;
    }

    container.innerHTML = groups.map(group => `
        <div class="group-item">
            <label class="group-checkbox">
                <input type="checkbox" value="${group.id}" 
                       onchange="toggleVkGroup('${group.id}')"
                       ${selectedVkGroups.includes(group.id) ? 'checked' : ''}>
                <span>${group.name}</span>
            </label>
            <button class="delete-btn" onclick="deleteVkGroup('${group.id}')" title="Delete">✕</button>
        </div>
    `).join('');
}

// отрисовка tg каналов
function renderTgChannels(channels) {
    const container = document.getElementById('tgChannelsList');

    if (!container) return;

    if (channels.length === 0) {
        container.innerHTML = '<div class="no-groups">NO CHANNELS SAVED</div>';
        return;
    }

    container.innerHTML = channels.map(channel => `
        <div class="group-item">
            <label class="group-checkbox">
                <input type="checkbox" value="${channel.id}"
                       onchange="toggleTgChannel('${channel.id}')"
                       ${selectedTgChannels.includes(channel.id) ? 'checked' : ''}>
                <span>${channel.name}</span>
            </label>
            <button class="delete-btn" onclick="deleteTgChannel('${channel.id}')" title="Delete">✕</button>
        </div>
    `).join('');
}

// переключение vk группы
function toggleVkGroup(groupId) {
    const index = selectedVkGroups.indexOf(groupId);
    if (index > -1) {
        selectedVkGroups.splice(index, 1);
    } else {
        selectedVkGroups.push(groupId);
    }
    updateVkCount();
}

// переключение tg канала
function toggleTgChannel(channelId) {
    const index = selectedTgChannels.indexOf(channelId);
    if (index > -1) {
        selectedTgChannels.splice(index, 1);
    } else {
        selectedTgChannels.push(channelId);
    }
    updateTgCount();
}

// обновление счетчика vk
function updateVkCount() {
    const countEl = document.getElementById('vkSelectedCount');
    if (countEl) {
        countEl.textContent = selectedVkGroups.length;
    }
}

// обновление счетчика tg
function updateTgCount() {
    const countEl = document.getElementById('tgSelectedCount');
    if (countEl) {
        countEl.textContent = selectedTgChannels.length;
    }
}

// открытие/закрытие vk dropdown
function toggleVkDropdown() {
    const dropdown = document.getElementById('vkDropdown');
    if (!dropdown) return;

    const isOpen = dropdown.style.display === 'block';
    closeAllDropdowns();
    if (!isOpen) {
        dropdown.style.display = 'block';
    }
}

function closeVkDropdown() {
    const dropdown = document.getElementById('vkDropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
}

// открытие/закрытие tg dropdown
function toggleTgDropdown() {
    const dropdown = document.getElementById('tgDropdown');
    if (!dropdown) return;

    const isOpen = dropdown.style.display === 'block';
    closeAllDropdowns();
    if (!isOpen) {
        dropdown.style.display = 'block';
    }
}

function closeTgDropdown() {
    const dropdown = document.getElementById('tgDropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
}

// закрыть все выпадающие списки
function closeAllDropdowns() {
    const vkDropdown = document.getElementById('vkDropdown');
    const tgDropdown = document.getElementById('tgDropdown');

    if (vkDropdown) vkDropdown.style.display = 'none';
    if (tgDropdown) tgDropdown.style.display = 'none';
}

// переключение подсказок
function toggleTooltip(tooltipId) {
    const tooltip = document.getElementById(tooltipId);
    if (!tooltip) return;

    const isVisible = tooltip.style.display === 'block';

    document.querySelectorAll('.tooltip-content').forEach(t => {
        t.style.display = 'none';
    });

    if (!isVisible) {
        tooltip.style.display = 'block';
    }
}

// форматирование текста
window.insertFormatting = function(type) {
    const textarea = document.getElementById('postText');
    if (!textarea) return;

    let startTag = '', endTag = '';
    switch(type) {
        case 'bold':
            startTag = '<b>';
            endTag = '</b>';
            break;
        case 'italic':
            startTag = '<i>';
            endTag = '</i>';
            break;
        case 'mono':
            startTag = '<code>';
            endTag = '</code>';
            break;
        case 'strike':
            startTag = '<s>';
            endTag = '</s>';
            break;
        case 'underline':
            startTag = '<u>';
            endTag = '</u>';
            break;
    }

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    const selectedText = text.slice(start, end);

    textarea.value = text.slice(0, start) + startTag + selectedText + endTag + text.slice(end);
    textarea.focus();
    textarea.selectionStart = start + startTag.length;
    textarea.selectionEnd = start + startTag.length + selectedText.length;
}

// удаление vk группы
async function deleteVkGroup(groupId) {
    if (!confirm('Delete this group?')) return;

    try {
        const response = await fetch('/api/remove-vk-group-token/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ group_id: groupId })
        });

        const data = await response.json();
        if (data.success) {
            selectedVkGroups = selectedVkGroups.filter(id => id !== groupId);
            updateVkCount();
            loadSavedGroups();
        } else {
            alert('Delete error: ' + data.error);
        }
    } catch (error) {
        alert('Connection error: ' + error.message);
    }
}

// удаление tg канала
async function deleteTgChannel(channelId) {
    if (!confirm('Delete this channel?')) return;

    try {
        const response = await fetch('/api/remove-tg-channel/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ channel_id: channelId })
        });

        const data = await response.json();
        if (data.success) {
            selectedTgChannels = selectedTgChannels.filter(id => id !== channelId);
            updateTgCount();
            loadSavedGroups();
        } else {
            alert('Delete error: ' + data.error);
        }
    } catch (error) {
        alert('Connection error: ' + error.message);
    }
}

// функция публикации поста
async function publishPost() {
    const postText = document.getElementById('postText');
    const fileInput = document.getElementById('fileInput');
    const fileName = document.getElementById('fileName');
    const publishBtn = document.getElementById('publishBtn');

    if (!postText || !fileInput || !publishBtn) return;

    const text = postText.value.trim();
    const files = fileInput.files;

    if (!text && files.length === 0) {
        alert('Add text or image');
        return;
    }

    if (selectedVkGroups.length === 0 && selectedTgChannels.length === 0) {
        alert('Select at least one VK group or Telegram channel from the list');
        return;
    }

    const formData = new FormData();
    formData.append('text', text);
    formData.append('vk_groups', selectedVkGroups.join(','));
    formData.append('tg_channels', selectedTgChannels.join(','));

    if (scheduledTime) {
        formData.append('scheduled_time', scheduledTime);
    }

    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    publishBtn.disabled = true;
    publishBtn.textContent = scheduledTime ? 'SCHEDULING...' : 'PUBLISHING...';

    try {
        const response = await fetch('/api/publish-post/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            if (scheduledTime) {
                alert('Post scheduled! It will be published at the specified time.');
            } else {
                alert('Post published successfully!');
            }

            postText.value = '';
            fileInput.value = '';
            if (fileName) fileName.textContent = '';

            selectedVkGroups = [];
            selectedTgChannels = [];
            scheduledTime = null;
            updateVkCount();
            updateTgCount();
            loadSavedGroups();
            loadRecentPosts();
        } else {
            let errorMsg = scheduledTime ? 'Scheduling error:\n' : 'Publishing error:\n';

            if (data.errors && data.errors.length > 0) {
                errorMsg += data.errors.join('\n');
            } else {
                errorMsg += data.error || 'Unknown error';
            }

            alert(errorMsg);
        }
    } catch (error) {
        alert('Connection error: ' + error.message);
    } finally {
        publishBtn.disabled = false;
        publishBtn.textContent = 'PUBLISH';
    }
}

// обновление превью запланированного времени
function updateSchedulePreview() {
    const scheduleDateInput = document.getElementById('scheduleDate');
    const scheduleTimeInput = document.getElementById('scheduleTime');
    const schedulePreview = document.getElementById('schedulePreview');
    const publishLaterBtn = document.getElementById('publishLaterBtn');

    if (!scheduleDateInput || !scheduleTimeInput || !schedulePreview || !publishLaterBtn) return;

    const date = scheduleDateInput.value;
    const time = scheduleTimeInput.value;

    if (date && time) {
        const scheduled = new Date(`${date}T${time}`);
        const now = new Date();

        if (scheduled <= now) {
            schedulePreview.innerHTML = '<span style="color: #000000;">CHOSEN TIME IS IN THE PAST</span>';
            publishLaterBtn.disabled = true;
        } else {
            const diff = scheduled - now;
            const hours = Math.floor(diff / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

            const day = String(scheduled.getDate()).padStart(2, '0');
            const month = String(scheduled.getMonth() + 1).padStart(2, '0');
            const year = scheduled.getFullYear();
            const hour = String(scheduled.getHours()).padStart(2, '0');
            const minute = String(scheduled.getMinutes()).padStart(2, '0');

            const formattedDateTime = `${day}/${month}/${year} ${hour}:${minute}`;

            schedulePreview.innerHTML = `
                <strong>POST SCHEDULED FOR:</strong><br>
                ${formattedDateTime}<br>
                <span style="color: #888;">(in ${hours}h ${minutes}min)</span>
            `;
            publishLaterBtn.disabled = false;
        }
    }
}

// инициализация
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing...');

    const scheduleBtn = document.getElementById('scheduleBtn');
    const scheduleModal = document.getElementById('scheduleModal');
    const closeScheduleModal = document.getElementById('closeScheduleModal');
    const scheduleDateInput = document.getElementById('scheduleDate');
    const scheduleTimeInput = document.getElementById('scheduleTime');
    const publishNowBtn = document.getElementById('publishNowBtn');
    const publishLaterBtn = document.getElementById('publishLaterBtn');
    const fileInput = document.getElementById('fileInput');
    const fileName = document.getElementById('fileName');
    const publishBtn = document.getElementById('publishBtn');
    const profileModal = document.getElementById('profileModal');
    const openProfileBtn = document.getElementById('openProfileModal');
    const closeProfileBtn = document.getElementById('closeProfileModal');
    const tgModal = document.getElementById('tgModal');
    const openTgModalBtn = document.getElementById('openTgModal');
    const closeTgModalBtn = document.getElementById('closeTgModal');
    const toggleVkBtn = document.getElementById('toggleVkList');
    const toggleTgBtn = document.getElementById('toggleTgList');
    const vkGroupIdInput = document.querySelector('#vkConnectBtn .social-group-id');
    const vkGroupTokenInput = document.querySelector('#vkConnectBtn .social-group-token');
    const vkAddBtn = document.querySelector('#vkConnectBtn .social-add-btn');
    const tgInput = document.querySelector('#tgConnectBtn .social-input');
    const tgAddBtn = document.querySelector('#tgConnectBtn .social-add-btn');
    const tgSendCodeBtn = document.getElementById('tgSendCodeBtn');
    const tgVerifyCodeBtn = document.getElementById('tgVerifyCodeBtn');

    // установка минимальной даты
    if (scheduleDateInput) {
        const today = new Date().toISOString().split('T')[0];
        scheduleDateInput.setAttribute('min', today);
    }

    // планирование
    if (scheduleBtn && scheduleModal) {
        scheduleBtn.addEventListener('click', function() {
            scheduleModal.style.display = 'block';
            setTimeout(() => {
                scheduleModal.classList.add('active');
            }, 10);

            if (scheduleDateInput && !scheduleDateInput.value) {
                const today = new Date().toISOString().split('T')[0];
                scheduleDateInput.value = today;
            }
            if (scheduleTimeInput && !scheduleTimeInput.value) {
                const now = new Date();
                const hours = String(now.getHours()).padStart(2, '0');
                const minutes = String(now.getMinutes()).padStart(2, '0');
                scheduleTimeInput.value = `${hours}:${minutes}`;
            }
            updateSchedulePreview();
        });
    }

    if (closeScheduleModal && scheduleModal) {
        closeScheduleModal.addEventListener('click', () => closeModal(scheduleModal));
    }

    if (scheduleDateInput) {
        scheduleDateInput.addEventListener('change', updateSchedulePreview);
    }

    if (scheduleTimeInput) {
        scheduleTimeInput.addEventListener('input', updateSchedulePreview);
    }

    if (publishNowBtn && scheduleModal) {
        publishNowBtn.addEventListener('click', function() {
            scheduledTime = null;
            closeModal(scheduleModal);
            publishPost();
        });
    }

    if (publishLaterBtn && scheduleModal) {
        publishLaterBtn.addEventListener('click', function() {
            if (!scheduleDateInput || !scheduleTimeInput) return;

            const date = scheduleDateInput.value;
            const time = scheduleTimeInput.value;

            if (!date || !time) {
                alert('Choose date and time');
                return;
            }

            const scheduled = new Date(`${date}T${time}`);
            const now = new Date();

            if (scheduled <= now) {
                alert('Chosen time is in the past');
                return;
            }

            scheduledTime = scheduled.toISOString();
            closeModal(scheduleModal);
            publishPost();
        });
    }

    // кнопки toggle
    if (toggleVkBtn) {
        toggleVkBtn.addEventListener('click', function(e) {
            if (this.disabled || this.classList.contains('disabled')) {
                e.preventDefault();
                return;
            }
            toggleVkDropdown();
        });
    }

    if (toggleTgBtn) {
        toggleTgBtn.addEventListener('click', function(e) {
            if (this.disabled || this.classList.contains('disabled')) {
                e.preventDefault();
                return;
            }
            toggleTgDropdown();
        });
    }

    // файлы
    if (fileInput && fileName) {
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                const names = Array.from(this.files).map(f => f.name).join(', ');
                fileName.textContent = names;
            } else {
                fileName.textContent = '';
            }
        });
    }

    // добавление vk группы
    if (vkAddBtn && vkGroupIdInput && vkGroupTokenInput) {
        vkAddBtn.addEventListener('click', async function() {
            const groupId = vkGroupIdInput.value.trim();
            const groupToken = vkGroupTokenInput.value.trim();

            if (!groupId || !groupToken) {
                alert('Enter group ID and access token');
                return;
            }

            try {
                const response = await fetch('/api/save-vk-group-token/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        group_id: groupId,
                        group_token: groupToken
                    })
                });

                const data = await response.json();

                if (data.success) {
                    vkGroupIdInput.value = '';
                    vkGroupTokenInput.value = '';
                    alert(`VK group ${groupId} added`);
                    loadSavedGroups();
                } else {
                    alert('Error: ' + (data.error || 'failed to save token'));
                }
            } catch (error) {
                alert('Connection error: ' + error.message);
            }
        });
    }

    // добавление tg канала
    if (tgAddBtn && tgInput) {
        tgAddBtn.addEventListener('click', async function() {
            const channelId = tgInput.value.trim();

            if (!channelId) {
                alert('Enter channel ID');
                return;
            }

            try {
                const response = await fetch('/api/save-tg-channel/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        channel_id: channelId,
                        channel_name: channelId
                    })
                });

                const data = await response.json();

                if (data.success) {
                    tgInput.value = '';
                    alert(`Telegram channel ${channelId} added`);
                    loadSavedGroups();
                } else {
                    alert('Error: ' + (data.error || 'failed to save channel'));
                }
            } catch (error) {
                alert('Connection error: ' + error.message);
            }
        });
    }

    // публикация
    if (publishBtn) {
        publishBtn.addEventListener('click', function() {
            if (scheduleModal) {
                scheduleModal.style.display = 'block';
                setTimeout(() => {
                    scheduleModal.classList.add('active');
                }, 10);
                updateSchedulePreview();
            }
        });
    }

    // окно профиля
    if (openProfileBtn && profileModal) {
        openProfileBtn.addEventListener('click', function() {
            profileModal.style.display = 'block';
            setTimeout(() => {
                profileModal.classList.add('active');
            }, 10);
        });
    }

    if (closeProfileBtn && profileModal) {
        closeProfileBtn.addEventListener('click', () => closeModal(profileModal));
    }

    // окно tg
    if (openTgModalBtn && tgModal) {
        openTgModalBtn.addEventListener('click', function() {
            tgModal.style.display = 'block';
            setTimeout(() => {
                tgModal.classList.add('active');
            }, 10);
        });
    }

    if (closeTgModalBtn && tgModal) {
        closeTgModalBtn.addEventListener('click', () => closeModal(tgModal));
    }

    // tg авторизация
    if (tgSendCodeBtn) {
        tgSendCodeBtn.addEventListener('click', async function() {
            const tgErrorMessage = document.getElementById('tg-error-message');
            const tgPhone = document.getElementById('tgPhone');

            if (!tgPhone) return;

            if (tgErrorMessage) tgErrorMessage.style.display = 'none';

            const phone = tgPhone.value.trim();
            if (!phone) {
                if (tgErrorMessage) {
                    tgErrorMessage.textContent = 'Enter phone number';
                    tgErrorMessage.style.display = 'block';
                }
                return;
            }

            tgSendCodeBtn.disabled = true;
            tgSendCodeBtn.textContent = 'SENDING...';

            try {
                const response = await fetch('/api/tg-send-code/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({ phone: phone })
                });

                const data = await response.json();

                if (data.success) {
                    const tgStep1 = document.getElementById('tgStep1');
                    const tgStep2 = document.getElementById('tgStep2');
                    if (tgStep1) tgStep1.style.display = 'none';
                    if (tgStep2) tgStep2.style.display = 'block';
                } else {
                    if (tgErrorMessage) {
                        tgErrorMessage.textContent = data.error || 'Code sending error';
                        tgErrorMessage.style.display = 'block';
                    }
                }
            } catch (e) {
                if (tgErrorMessage) {
                    tgErrorMessage.textContent = 'Connection error';
                    tgErrorMessage.style.display = 'block';
                }
            } finally {
                tgSendCodeBtn.disabled = false;
                tgSendCodeBtn.textContent = 'GET CODE';
            }
        });
    }

    if (tgVerifyCodeBtn) {
        tgVerifyCodeBtn.addEventListener('click', async function() {
            const tgErrorMessage = document.getElementById('tg-error-message');
            const tgCode = document.getElementById('tgCode');
            const tg2faPassword = document.getElementById('tg2faPassword');

            if (!tgCode) return;

            if (tgErrorMessage) tgErrorMessage.style.display = 'none';

            const code = tgCode.value.trim();
            const password = tg2faPassword ? tg2faPassword.value : '';

            if (!code) {
                if (tgErrorMessage) {
                    tgErrorMessage.textContent = 'Enter code';
                    tgErrorMessage.style.display = 'block';
                }
                return;
            }

            tgVerifyCodeBtn.disabled = true;
            tgVerifyCodeBtn.textContent = 'VERIFYING...';

            try {
                const response = await fetch('/api/tg-verify-code/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({ code: code, password: password })
                });

                const data = await response.json();

                if (data.success) {
                    window.location.reload();
                } else if (data.error === '2fa_required') {
                    const tg2faGroup = document.getElementById('tg2faGroup');
                    if (tg2faGroup) tg2faGroup.style.display = 'block';
                    if (tgErrorMessage) {
                        tgErrorMessage.textContent = '2FA password required';
                        tgErrorMessage.style.display = 'block';
                    }
                } else {
                    if (tgErrorMessage) {
                        tgErrorMessage.textContent = data.error || 'Verification error';
                        tgErrorMessage.style.display = 'block';
                    }
                }
            } catch (e) {
                if (tgErrorMessage) {
                    tgErrorMessage.textContent = 'Connection error';
                    tgErrorMessage.style.display = 'block';
                }
            } finally {
                tgVerifyCodeBtn.disabled = false;
                tgVerifyCodeBtn.textContent = 'CONFIRM';
            }
        });
    }

    // загрузка данных
    const isUserLoggedIn = document.body.dataset.userLoggedIn === 'true';
    if (isUserLoggedIn) {
        loadSavedGroups();
        loadRecentPosts();
    }

    // хоткеи для форматирования текста
    const postTextArea = document.getElementById('postText');
    if (postTextArea) {
        postTextArea.addEventListener('keydown', function(e) {
            if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey) {
                let type = null;
                switch (e.key.toLowerCase()) {
                    case 'b':
                        type = 'bold';
                        break;
                    case 'i':
                        type = 'italic';
                        break;
                    case 'm':
                        type = 'mono';
                        break;
                    case 's':
                        type = 'strike';
                        break;
                    case 'u':
                        type = 'underline';
                        break;
                }

                if (type) {
                    e.preventDefault();
                    window.insertFormatting(type);
                }
            }
        });
    }

    console.log('Initialization complete!');
});

// глобальные обработчики

// закрытие dropdown при клике вне
document.addEventListener('click', function(e) {
    if (!e.target.closest('.dropdown-panel') &&
        !e.target.closest('.list-toggle-btn')) {
        closeAllDropdowns();
    }

    // закрытие подсказок
    if (!e.target.closest('.tooltip-trigger') &&
        !e.target.closest('.tooltip-content')) {
        document.querySelectorAll('.tooltip-content').forEach(t => {
            t.style.display = 'none';
        });
    }
});

// закрытие модальных окон при клике вне
window.addEventListener('click', function(event) {
    const profileModal = document.getElementById('profileModal');
    const tgModal = document.getElementById('tgModal');
    const scheduleModal = document.getElementById('scheduleModal');

    if (event.target === profileModal) {
        closeModal(profileModal);
    }
    if (event.target === tgModal) {
        closeModal(tgModal);
    }
    if (event.target === scheduleModal) {
        closeModal(scheduleModal);
    }
});
