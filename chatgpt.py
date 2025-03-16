from g4f.client import Client


client = Client()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Напишите описание товара для интернет-магазина автозапчастей. Товар: 'Тяга стабилизатора передней подвески для Opel Vectra B'. Описание должно быть длиной 50 слов, информативным, с использованием ключевых слов для улучшения поисковой оптимизации (SEO). Включите следующие аспекты:\n\nНазначение детали (тяга стабилизатора передней подвески).\nСовместимость с автомобилем (Opel Vectra B, указать годы выпуска 1995–2002).\nПреимущества (например, долговечность, качество, улучшение управляемости).\nУкажите OEM-номер (например, 350610) и, по возможности, найдите другие OEM-номера (например, 90496116), добавьте их в описание.\nУкажите популярные бренды-аналоги (TRW, Lemförder, Febi).\nКлючевые слова для поиска: тяга стабилизатора Opel Vectra B, передняя стойка стабилизатора, запчасти Opel Vectra B, стабилизатор подвески Vectra B, купить тягу стабилизатора.\nСделайте текст естественным, продающим и понятным для покупателей, избегая избыточной технической терминологии."}],
    web_search=True
)
print(response.choices[0].message.content)











# from g4f.client import Client

# client = Client()
# response = client.images.generate(
#     model="flux",
#     prompt="a white siamese cat",
#     response_format="url"
# )

# print(f"Generated image URL: {response.data[0].url}")


