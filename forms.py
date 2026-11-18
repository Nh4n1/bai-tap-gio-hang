from datetime import datetime

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import (
    FileField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class CategoryForm(FlaskForm):

    name = StringField(
        "Tên danh mục",
        validators=[
            DataRequired(message="Vui lòng nhập tên danh mục"),
            Length(max=100)
        ]
    )

    description = TextAreaField(
        "Mô tả",
        validators=[Optional()]
    )

    submit = SubmitField("Lưu danh mục")
    
    


class BookForm(FlaskForm):

    title = StringField(
        "Tên sách",
        validators=[
            DataRequired(message="Vui lòng nhập tên sách"),
            Length(max=200)
        ]
    )

    author = StringField(
        "Tác giả",
        validators=[
            DataRequired(message="Vui lòng nhập tên tác giả"),
            Length(max=150)
        ]
    )

    publisher = StringField(
        "Nhà xuất bản",
        validators=[Optional(), Length(max=150)]
    )

    publish_year = IntegerField(
        "Năm xuất bản",
        validators=[
            Optional(),
            NumberRange(
                min=1900,
                max=datetime.now().year,
                message="Năm xuất bản không hợp lệ"
            )
        ]
    )

    price = IntegerField(
        "Giá bán",
        validators=[
            DataRequired(message="Vui lòng nhập giá"),
            NumberRange(
                min=1000,
                message="Giá sách phải từ 1.000 đồng"
            )
        ]
    )

    stock = IntegerField(
        "Số lượng tồn kho",
        validators=[
            DataRequired(message="Vui lòng nhập số lượng"),
            NumberRange(
                min=0,
                message="Số lượng tồn kho không được âm"
            )
        ]
    )

    category_id = SelectField(
        "Danh mục",
        coerce=int,
        validators=[DataRequired()]
    )

    description = TextAreaField(
        "Mô tả",
        validators=[Optional()]
    )

    image = FileField(
        "Ảnh bìa",
        validators=[
            Optional(),
            FileAllowed(
                ["jpg", "jpeg", "png", "webp"],
                "Chỉ chấp nhận JPG, PNG hoặc WEBP"
            )
        ]
    )

    submit = SubmitField("Lưu sách")