from flask import Flask, url_for, render_template, request, redirect
from googletrans import Translator
from flask_login import LoginManager, login_required, logout_user, \
    login_user, current_user
from data import db_session
from data.users import User
from forms.user import RegisterForm, LoginForm
from forms.settings import SettingsForm
from subprocess import Popen
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = "very_secret_key"
login_manager = LoginManager()
login_manager.init_app(app)

tr = Translator()
text_placeholder = ["Добро пожаловать!", "newpoint", "..."]


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


def theme_check(user):
    """
    Получение темы сайта из базы данных
    """
    if user.is_authenticated:
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(
            (User.login == current_user.login)
        ).first()
        theme = user.theme
        return theme
    else:
        return 'dark'


def translate_list(text: list, dest):
    """
    Перевод ответа AI Dungeon
    """
    global tr
    result = [x.text for x in tr.translate(text, dest=dest)]
    return result


def translate(text: str, dest):
    """
    Перевод ответа или запроса для AI Dungeon
    """
    global tr
    result = tr.translate(text, dest=dest).text
    return result


def check_file(file_name="output_data.txt"):
    """
    Проверяет, есть ли изменения в файле.
    Файл свежий в том случае, если содержит подтверждающий это атрибут.
    Если атрибут говорит, что файл обновлён, то возвращает истину и
    отмечает файл как 'не новый', а также извлекает содержимое.
    Если файл уже отмечен несвежим, то вернёт ложь.
    """
    global text_placeholder

    with open("output_is_checked.txt", mode="r") as file:
        response = file.read(1)
    is_checked = bool(int(response))
    # проверяет, вносились ли изменения
    if is_checked:
        # недавно проверялся, значит
        # ничего нового - расходимся
        return False
    # или есть что-то новое
    with open(file_name, mode="r", encoding="utf-8") as file:
        data = [
            x.strip().replace(
                '\n', r"<br>"
            ) for x in file.read().rstrip().split("<newline>")
        ]
    if not data[-1]:
        del data[-1]
    # убирает старый отделитель
    del text_placeholder[text_placeholder.index("newpoint")]
    # чистит избыточный текст
    if data and data[0] == "Generating story...":
        text_placeholder.clear()
    # добавляет новый
    text_placeholder.append("newpoint")
    text_placeholder += translate_list(data, 'ru').copy()
    # перезапись
    with open("output_is_checked.txt", mode="w") as file:
        file.write("1")
    return True


def write_prompt(text: str, file_name="input_data.txt"):
    """
        Запись сообщения пользователя в файл
    """
    with open("input_is_updated.txt", mode="r") as file:
        not_read = bool(int(file.read(1)))
    if not_read:
        # файл ещё не был прочитан
        return
    with open(file_name, mode="w") as file:
        file.write(text)
    with open("input_is_updated.txt", mode="w") as file:
        file.write("1")


@app.route("/")
def default_page():
    """
        Главная страница
    """

    return render_template("main.html", theme=theme_check(current_user))


@app.route("/chat", methods=['POST', 'GET'])
def chat_page():
    """
        Страница с игрой
    """
    global text_placeholder
    # print(text_placeholder[-1])
    if request.method == "POST" and request.form["text"] != "":
        # если есть действие, то...
        # print(translate(request.form["text"], 'en'))
        if not any(map(lambda x: x != ' ', request.form["text"])):
            # весь запрос - пробелы
            write_prompt("")
        elif request.form["text"] == "/launch":
            Popen("play.bat")
        elif (request.form["text"] == '1' and
              "1) Написать пользовательскую"
              " подсказку" in text_placeholder[-8:]):
            pass
        else:
            write_prompt(translate(request.form["text"], 'en'))
        return redirect("#scrollspyHeading1")

    elif request.method == "GET" or request.method == "POST":
        # добавляем данные при обновлении страницы
        check_file()

        return render_template(
            "chat.html",
            data=text_placeholder,
            theme=theme_check(current_user)
        )


@app.route("/settings", methods=['POST', 'GET'])
def settings_page():
    form = SettingsForm(request.form)
    if request.method == 'POST' and form.validate():
        if current_user.is_authenticated:
            db_sess = db_session.create_session()
            user = db_sess.query(User).filter(
                (User.login == current_user.login)
            ).first()
            user.theme = form.theme.data
            db_sess.commit()
    return render_template(
        "settings.html",
        form=form,
        theme=theme_check(current_user)
    )


@app.route("/load", methods=['POST', 'GET'])
def load_page():
    try:
        name = current_user.login
    except AttributeError:
        name = "anonymous"
    if request.method == 'GET':
        return render_template(
            "load.html", theme=theme_check(current_user)
        )
    elif request.method == 'POST':
        amount = str(len(os.listdir("./prompts/Custom"))) + '_'
        f = request.files['file']
        with open(
                f"./prompts/Custom/{amount + name}.txt",
                mode="wb") as file:
            file.write(f.read())
        return render_template(
            "success.html", theme=theme_check(current_user)
        )


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html',
                                   title='Регистрация',
                                   theme='dark',
                                   form=form,
                                   message="Пароли не совпадают")
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(
                User.login == form.login.data
        ).first():
            return render_template(
                'register.html',
                title='Регистрация',
                theme='dark',
                form=form,
                message="Такой пользователь уже есть"
            )
        user = User(login=form.login.data)
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        return redirect('/login')
    return render_template(
        'register.html',
        title='Регистрация',
        form=form,
        theme='dark'
    )


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    # подключение формы
    form = LoginForm()
    db_sess = db_session.create_session()
    if form.validate_on_submit():
        # поиск пользователя в базе
        user = db_sess.query(User).filter(
            User.login == form.login.data
        ).first()
        # проверка пароля
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            # активация сохранений
            if user.saved_games is not None:
                saves = user.saved_games.split()
                # print(saves)
                for save in saves:
                    try:
                        os.rename(f"./saves/{save}.txt",
                                  f"./saves/{save}.json")
                    except Exception as ex:
                        print(ex)
            return redirect("/")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form, theme='dark')
    return render_template(
        'login.html',
        title='Авторизация',
        form=form,
        theme=theme_check(current_user)
    )


@app.route('/logout')
@login_required
def logout():
    # сбор json'ов
    saves = [x for x in os.listdir("./saves") if x[-5:] == ".json"]
    # деактивация (смена расширения на txt)
    for save in saves:
        os.rename(f"./saves/{save}", f"./saves/{save[:-5]}.txt")
    # запись в пользователя
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(
        (User.login == current_user.login)
    ).first()
    user.saved_games = ' '.join([x[:-5] for x in saves])
    db_sess.commit()
    # конец =(
    logout_user()
    return redirect("/")


def main():
    db_session.global_init("db/users.db")
    app.run(port=8080, host="127.0.0.1")


if __name__ == '__main__':
    main()
