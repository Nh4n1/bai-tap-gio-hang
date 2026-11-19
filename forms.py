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
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    NumberRange,
    Optional,
    Regexp,
)


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
    



class OrderStatusForm(FlaskForm):

    status = SelectField(
        "Trạng thái đơn hàng",
        choices=[],
        validators=[
            DataRequired(message="Vui lòng chọn trạng thái")
        ]
    )

    submit = SubmitField("Cập nhật trạng thái")
    
    

class CheckoutForm(FlaskForm):

    # Họ tên khách hàng
    customer_name = StringField(
        "Họ tên",
        validators=[
            DataRequired(
                message="Vui lòng nhập họ tên!"
            ),
            Length(
                max=150,
                message="Họ tên không được vượt quá 150 ký tự!"
            )
        ]
    )

    # Số điện thoại
    phone = StringField(
        "Số điện thoại",
        validators=[
            DataRequired(
                message="Vui lòng nhập số điện thoại!"
            ),
            Regexp(
                r"^0\d{9}$",
                message="Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0!"
            )
        ]
    )

    # Email không bắt buộc
    email = StringField(
        "Email",
        validators=[
            Optional(),
            Email(
                message="Email không đúng định dạng!"
            ),
            Length(
                max=150,
                message="Email không được vượt quá 150 ký tự!"
            )
        ]
    )

    # Địa chỉ giao hàng
    address = StringField(
        "Địa chỉ giao hàng",
        validators=[
            DataRequired(
                message="Vui lòng nhập địa chỉ giao hàng!"
            ),
            Length(
                max=255,
                message="Địa chỉ không được vượt quá 255 ký tự!"
            )
        ]
    )

    # Ghi chú
    note = TextAreaField(
        "Ghi chú",
        validators=[
            Optional()
        ]
    )

    # Phương thức thanh toán
    payment_method = SelectField(
        "Phương thức thanh toán",
        choices=[
            ("cash", "Tiền mặt khi nhận hàng"),
            ("bank_transfer", "Chuyển khoản")
        ],
        validators=[
            DataRequired(
                message="Vui lòng chọn phương thức thanh toán!"
            )
        ]
    )

    # Nút xác nhận
    submit = SubmitField(
        "Xác nhận đặt hàng"
    )
