
import os
import uuid
from datetime import datetime

from flask import Flask, current_app, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from PIL import Image
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from config import Config
from forms import BookForm, CategoryForm

# config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
csrf = CSRFProtect(app) #learn about this


def save_book_image(image_file):

    if not image_file or not image_file.filename:
        return None

    # Lấy phần mở rộng của ảnh
    extension = image_file.filename.rsplit(".", 1)[-1].lower()

    # Kiểm tra định dạng ảnh
    allowed_extensions = ["jpg", "jpeg", "png", "webp"]

    if extension not in allowed_extensions:
        raise ValueError("Định dạng ảnh không được hỗ trợ!")

    # Kiểm tra kích thước file
    image_file.stream.seek(0, os.SEEK_END)
    file_size = image_file.stream.tell()
    image_file.stream.seek(0)

    if file_size > 2 * 1024 * 1024:
        raise ValueError("Ảnh không được vượt quá 2 MB!")

    # Kiểm tra nội dung file có thực sự là ảnh không
    try:
        image = Image.open(image_file.stream)
        image.verify()
    except Exception:
        raise ValueError("File tải lên không phải ảnh hợp lệ!")

    image_file.stream.seek(0)

    # Tạo tên file ngẫu nhiên
    filename = f"{uuid.uuid4().hex}.{extension}"

    upload_folder = current_app.config["UPLOAD_FOLDER"]

    os.makedirs(upload_folder, exist_ok=True)

    image_file.save(
        os.path.join(upload_folder, filename)
    )

    return filename


# model

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(100),
        nullable=False,
        unique=True
    )

    description = db.Column(db.Text)

    books = db.relationship(
        "Book",
        back_populates="category"
    )


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(150), nullable=False)
    publisher = db.Column(db.String(150))
    publish_year = db.Column(db.Integer)

    price = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)

    description = db.Column(db.Text)
    image = db.Column(db.String(255))

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=False
    )

    category = db.relationship(
        "Category",
        back_populates="books"
    )


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)

    customer_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(150))
    address = db.Column(db.String(255), nullable=False)

    note = db.Column(db.Text)

    payment_method = db.Column(
        db.String(50),
        nullable=False
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="pending"
    )

    subtotal = db.Column(db.Integer, nullable=False)
    shipping_fee = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.now
    )

    items = db.relationship(
        "OrderItem",
        back_populates="order"
    )

    histories = db.relationship(
        "OrderStatusHistory",
        back_populates="order"
    )

class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False
    )

    book_id = db.Column(
        db.Integer,
        db.ForeignKey("books.id"),
        nullable=False
    )

    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)

    order = db.relationship(
        "Order",
        back_populates="items"
    )

    book = db.relationship("Book")

class OrderStatusHistory(db.Model):
    __tablename__ = "order_status_histories"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False
    )

    status = db.Column(db.String(30), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.now
    )

    order = db.relationship(
        "Order",
        back_populates="histories"
    )

# create db
with app.app_context():
    db.create_all()
    

# [GET, POST] /admin/categories
@app.route("/admin/categories", methods=["GET", "POST"])
def admin_categories():

    form = CategoryForm()

    # Lấy danh sách danh mục và số lượng sách
    categories = (
        db.session.query(
            Category,
            func.count(Book.id).label("book_count")
        )
        .outerjoin(Book, Category.id == Book.category_id)
        .group_by(Category.id)
        .order_by(Category.id.desc())
        .all()
    )

    if form.validate_on_submit():

        name = form.name.data.strip()

        # Kiểm tra tên danh mục đã tồn tại chưa
        existing = Category.query.filter(
            func.lower(Category.name) == name.lower()
        ).first()

        if existing:
            flash("Danh mục đã tồn tại!", "danger")

        else:
            category = Category(
                name=name,
                description=form.description.data
            )

            db.session.add(category)
            db.session.commit()

            flash("Thêm danh mục thành công!", "success")

            return redirect(url_for("admin_categories"))

    return render_template(
        "admin/categories/index.html",
        categories=categories,
        form=form
    )

@app.route("/admin/categories/<int:category_id>/edit",
           methods=["GET", "POST"])
def edit_category(category_id):

    category = db.get_or_404(Category, category_id)

    form = CategoryForm(obj=category)

    if form.validate_on_submit():

        name = form.name.data.strip()

        # Kiểm tra trùng tên, loại trừ chính danh mục đang sửa
        existing = Category.query.filter(
            func.lower(Category.name) == name.lower(),
            Category.id != category.id
        ).first()

        if existing:
            flash("Tên danh mục đã tồn tại!", "danger")

        else:
            category.name = name
            category.description = form.description.data

            db.session.commit()

            flash("Cập nhật danh mục thành công!", "success")

            return redirect(url_for("admin_categories"))

    return render_template(
        "admin/categories/form.html",
        form=form,
        category=category
    )

@app.route("/admin/categories/<int:category_id>/delete",
           methods=["POST"])
def delete_category(category_id):

    category = db.get_or_404(Category, category_id)

    # Đếm số sách thuộc danh mục
    book_count = Book.query.filter_by(
        category_id=category.id
    ).count()

    if book_count > 0:

        flash(
            f"Không thể xóa danh mục {category.name}: "
            f"còn {book_count} sách!",
            "danger"
        )

    else:

        db.session.delete(category)
        db.session.commit()

        flash("Xóa danh mục thành công!", "success")

    return redirect(url_for("admin_categories"))


#[GET] /admin/books
@app.route("/admin/books")
def admin_books():

    # Lấy tham số tìm kiếm từ URL
    keyword = request.args.get("q", "").strip()

    category_id = request.args.get(
        "category_id",
        type=int
    )

    stock_filter = request.args.get("stock", "")

    page = request.args.get("page", 1, type=int)

    # Truy vấn ban đầu
    query = Book.query

    # 1. Tìm theo tên sách hoặc tác giả
    if keyword:

        query = query.filter(
            or_(
                Book.title.ilike(f"%{keyword}%"),
                Book.author.ilike(f"%{keyword}%")
            )
        )

    # 2. Lọc theo danh mục
    if category_id:

        query = query.filter(
            Book.category_id == category_id
        )

    # 3. Lọc theo tồn kho
    if stock_filter == "available":

        query = query.filter(Book.stock > 5)

    elif stock_filter == "low":

        query = query.filter(
            Book.stock.between(1, 5)
        )

    elif stock_filter == "out":

        query = query.filter(Book.stock == 0)

    # 4. Sắp xếp mới nhất trước
    query = query.order_by(Book.id.desc())

    # 5. Phân trang: 5 sách/trang
    pagination = query.paginate(
        page=page,
        per_page=5,
        error_out=False
    )

    # Lấy danh mục để hiển thị trong Select
    categories = Category.query.order_by(
        Category.name
    ).all()

    return render_template(
        "admin/books/index.html",
        pagination=pagination,
        books=pagination.items,
        categories=categories,
        keyword=keyword,
        category_id=category_id,
        stock_filter=stock_filter
    )

@app.route("/admin/books/new", methods=["GET", "POST"])
def create_book():

    form = BookForm()

    # Lấy danh mục từ database
    categories = Category.query.order_by(
        Category.name
    ).all()

    # Đưa danh mục vào SelectField
    form.category_id.choices = [
        (category.id, category.name)
        for category in categories
    ]

    if form.validate_on_submit():

        # Kiểm tra tên sách đã tồn tại chưa
        existing = Book.query.filter(
            func.lower(Book.title) == form.title.data.strip().lower()
        ).first()

        if existing:

            form.title.errors.append(
                "Tên sách đã tồn tại!"
            )

        else:

            try:

                # Lưu ảnh nếu người dùng chọn ảnh
                image_name = save_book_image(
                    form.image.data
                )

                book = Book(
                    title=form.title.data.strip(),
                    author=form.author.data.strip(),
                    publisher=form.publisher.data,
                    publish_year=form.publish_year.data,
                    price=form.price.data,
                    stock=form.stock.data,
                    description=form.description.data,
                    image=image_name,
                    category_id=form.category_id.data
                )

                db.session.add(book)
                db.session.commit()

                flash("Thêm sách thành công!", "success")

                return redirect(url_for("admin_books"))

            except ValueError as error:

                db.session.rollback()

                flash(str(error), "danger")

            except Exception:

                db.session.rollback()

                flash("Có lỗi xảy ra khi thêm sách!", "danger")

    return render_template(
        "admin/books/form.html",
        form=form,
        book=None
    )

@app.route("/admin/books/<int:book_id>/edit",
           methods=["GET", "POST"])
def edit_book(book_id):

    book = db.get_or_404(Book, book_id)

    form = BookForm(obj=book)

    categories = Category.query.order_by(
        Category.name
    ).all()

    form.category_id.choices = [
        (category.id, category.name)
        for category in categories
    ]

    if form.validate_on_submit():

        title = form.title.data.strip()

        existing = Book.query.filter(
            func.lower(Book.title) == title.lower(),
            Book.id != book.id
        ).first()

        if existing:

            form.title.errors.append(
                "Tên sách đã tồn tại!"
            )

        else:

            old_image = book.image
            new_image = None

            try:

                # Nếu chọn ảnh mới thì lưu ảnh
                if form.image.data:
                    new_image = save_book_image(
                        form.image.data
                    )

                book.title = title
                book.author = form.author.data.strip()
                book.publisher = form.publisher.data
                book.publish_year = form.publish_year.data
                book.price = form.price.data
                book.stock = form.stock.data
                book.description = form.description.data
                book.category_id = form.category_id.data

                # Chỉ thay ảnh khi có ảnh mới
                if new_image:
                    book.image = new_image

                db.session.commit()

                # Xóa ảnh cũ sau khi cập nhật database thành công
                if new_image and old_image:

                    old_path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"],
                        old_image
                    )

                    if os.path.isfile(old_path):
                        os.remove(old_path)

                flash("Cập nhật sách thành công!", "success")

                return redirect(url_for("admin_books"))

            except ValueError as error:

                db.session.rollback()

                if new_image:
                    new_path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"],
                        new_image
                    )

                    if os.path.isfile(new_path):
                        os.remove(new_path)

                flash(str(error), "danger")

            except Exception:

                db.session.rollback()

                if new_image:
                    new_path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"],
                        new_image
                    )

                    if os.path.isfile(new_path):
                        os.remove(new_path)

                flash("Có lỗi xảy ra khi cập nhật sách!", "danger")

    return render_template(
        "admin/books/form.html",
        form=form,
        book=book
    )
    
@app.route("/admin/books/<int:book_id>/delete",
           methods=["POST"])
def delete_book(book_id):

    book = db.get_or_404(Book, book_id)

    # Kiểm tra sách đã xuất hiện trong đơn hàng chưa
    order_count = OrderItem.query.filter_by(
        book_id=book.id
    ).count()

    if order_count > 0:

        flash(
            "Không thể xóa sách đã xuất hiện trong đơn hàng!",
            "danger"
        )

        return redirect(url_for("admin_books"))

    try:

        image_name = book.image

        db.session.delete(book)
        db.session.commit()

        # Xóa ảnh sau khi xóa database thành công
        if image_name:

            image_path = os.path.join(
                current_app.config["UPLOAD_FOLDER"],
                image_name
            )

            if os.path.isfile(image_path):
                os.remove(image_path)

        flash("Xóa sách thành công!", "success")

    except Exception:

        db.session.rollback()

        flash("Không thể xóa sách!", "danger")

    return redirect(url_for("admin_books"))

###
# run
###
if __name__ == "__main__":
    app.run(debug=True, port=8000)
