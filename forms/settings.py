from flask_wtf import FlaskForm
from wtforms import SelectField


class SettingsForm(FlaskForm):
    theme = SelectField('Тема сайта', choices=[('light', 'Светлая'), ('dark', 'Тёмная')])
