document.addEventListener('DOMContentLoaded', () => {
    
    // ==========================================
    // 1. ЛОГИКА ДЛЯ ЛЕНТЫ (ЛАЙТБОКС)
    // ==========================================
    const lightbox = document.getElementById('memeLightbox');
    const lightboxImg = document.getElementById('lightboxImg');
    const closeBtn = document.querySelector('.close-btn');
    const imageWrappers = document.querySelectorAll('.meme-image-wrapper');

    if (lightbox && lightboxImg) {
        // Навешиваем событие клика на каждую картинку в ленте
        imageWrappers.forEach(wrapper => {
            wrapper.addEventListener('click', () => {
                const imgSrc = wrapper.getAttribute('data-src');
                if (imgSrc) {
                    lightboxImg.src = imgSrc;
                    lightbox.classList.add('active');
                    document.body.style.overflow = 'hidden'; // Отключаем скролл страницы
                }
            });
        });

        // Функция закрытия лайтбокса
        const closeLightbox = () => {
            lightbox.classList.remove('active');
            document.body.style.overflow = ''; // Возвращаем скролл
        };

        // Закрытие по клику на фон или крестик
        lightbox.addEventListener('click', (e) => {
            if (e.target === lightbox || e.target === closeBtn) {
                closeLightbox();
            }
        });

        // Закрытие по нажатию на клавишу Esc
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && lightbox.classList.contains('active')) {
                closeLightbox();
            }
        });
    }

    // ==========================================
    // 2. ЛОГИКА ДЛЯ AI-ЧАТА
    // ==========================================
    const chatMessages = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const attachBtn = document.getElementById('attachBtn');
    const fileInput = document.getElementById('fileInput');

    if (chatMessages && chatInput && sendBtn) {
        let selectedImageBase64 = null;

        // Обработка прикрепления файла (скрепка)
        if (attachBtn && fileInput) {
            attachBtn.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        // Убираем префикс "data:image/jpeg;base64," для отправки на сервер
                        selectedImageBase64 = event.target.result.split(',')[1];
                        chatInput.placeholder = "Картинка прикреплена. Напишите текст...";
                        chatInput.focus();
                    };
                    reader.readAsDataURL(file);
                }
            });
        }

        // Отправка сообщения
        async function sendMessage() {
            const text = chatInput.value.trim();
            if (!text && !selectedImageBase64) return;

            // Показываем сообщение пользователя
            if (selectedImageBase64) {
                const userBubble = addMessage(text || "Вот картинка", 'user').querySelector('.message-bubble');
                const img = document.createElement('img');
                img.src = `data:image/jpeg;base64,${selectedImageBase64}`;
                img.className = 'chat-image';
                img.style.maxWidth = '200px'; // Ограничиваем размер превью
                userBubble.appendChild(img);
            } else {
                addMessage(text, 'user');
            }

            // Формируем данные для отправки
            const payload = { text: text, image: selectedImageBase64 };
            
            // Очищаем поле ввода
            chatInput.value = '';
            chatInput.placeholder = "Напиши запрос...";
            selectedImageBase64 = null; // Сбрасываем картинку

            // Показываем "думает..."
            const loadingMsg = addMessage('Нейросеть думает...', 'ai', true);

            try {
                const resp = await fetch('/api/ai/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                
                loadingMsg.remove(); // Убираем "думает..."
                
                // Обработка ответов от сервера
                if (data.meme_url) {
                    // Пришел готовый мем (картинка + текст)
                    const bubble = addMessage(`Текст мема: "${data.caption}"`, 'ai').querySelector('.message-bubble');
                    const img = document.createElement('img');
                    img.src = data.meme_url;
                    img.className = 'chat-image';
                    bubble.appendChild(img);
                } 
                else if (data.image) {
                    // Пришла просто сгенерированная картинка (base64)
                    const bubble = addMessage('', 'ai').querySelector('.message-bubble');
                    const img = document.createElement('img');
                    img.src = `data:image/jpeg;base64,${data.image}`;
                    img.className = 'chat-image';
                    bubble.appendChild(img);
                }
                else if (data.answer) {
                    // Пришел обычный текст
                    addMessage(data.answer, 'ai');
                } 
                else {
                    // Пришла ошибка
                    addMessage('Ошибка: ' + (data.error || 'неизвестная ошибка'), 'ai');
                }
            } catch (e) {
                loadingMsg.remove();
                addMessage('Ошибка соединения: ' + e.message, 'ai');
            }
        }

        // Вспомогательная функция добавления сообщения в чат
        function addMessage(text, sender, isTemp = false) {
            const div = document.createElement('div');
            div.className = 'message ' + sender;
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = sender === 'ai' ? '🤖' : 'Я';
            
            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            if (text) bubble.textContent = text;
            
            div.appendChild(avatar);
            div.appendChild(bubble);
            chatMessages.appendChild(div);
            
            // Прокрутка вниз
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return div;
        }

        // Слушатели событий для чата
        sendBtn.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
});