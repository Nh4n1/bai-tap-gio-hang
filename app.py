
import os
import uuid
from datetime import datetime

from flask import Flask, current_app, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from PIL import Image
from sqlalchemy import extract, func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from config import Config
from forms import BookForm, CategoryForm, OrderStatusForm

# config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
csrf = CSRFProtect(app) #learn about this


ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_SHIPPING = "shipping"
ORDER_STATUS_COMPLETED = "completed"
ORDER_STATUS_CANCELLED = "cancelled"


ORDER_STATUS_LABELS = {
    ORDER_STATUS_PENDING: "Chờ xác nhận",
    ORDER_STATUS_SHIPPING: "Đang giao",
    ORDER_STATUS_COMPLETED: "Hoàn tất",
    ORDER_STATUS_CANCELLED: "Đã hủy"
}

ORDER_STATUS_TRANSITIONS = {
    ORDER_STATUS_PENDING: [
        ORDER_STATUS_SHIPPING,
        ORDER_STATUS_CANCELLED
    ],

    ORDER_STATUS_SHIPPING: [
        ORDER_STATUS_COMPLETED,
        ORDER_STATUS_CANCELLED
    ],

    ORDER_STATUS_COMPLETED: [],

    ORDER_STATUS_CANCELLED: []
}

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



@app.route("/")
def index():
    return redirect(url_for("admin_dashboard"))


@app.route("/admin")
def admin_dashboard():

    # 1. Tổng số đầu sách
    total_books = db.session.scalar(
        db.select(func.count(Book.id))
    )

    # 2. Số đơn hàng đang chờ xác nhận
    pending_orders = db.session.scalar(
        db.select(func.count(Order.id))
        .where(Order.status == ORDER_STATUS_PENDING)
    )

    # 3. Doanh thu tháng hiện tại
    now = datetime.now()

    monthly_revenue = db.session.scalar(
        db.select(func.coalesce(func.sum(Order.total), 0))
        .where(
            Order.status == ORDER_STATUS_COMPLETED,
            extract("year", Order.created_at) == now.year,
            extract("month", Order.created_at) == now.month
        )
    )

    # 4. Số sách có tồn kho <= 5
    low_stock_count = db.session.scalar(
        db.select(func.count(Book.id))
        .where(Book.stock <= 5)
    )

    # 5. Lấy 5 đơn hàng mới nhất
    recent_orders = db.session.scalars(
        db.select(Order)
        .order_by(Order.created_at.desc())
        .limit(5)
    ).all()

    # 6. Lấy danh sách sách sắp hết hàng
    low_stock_books = db.session.scalars(
        db.select(Book)
        .where(Book.stock <= 5)
        .order_by(Book.stock.asc())
        .limit(10)
    ).all()

    return render_template(
        "admin/dashboard.html",
        now_month=now.month,
        total_books=total_books,
        pending_orders=pending_orders,
        monthly_revenue=monthly_revenue,
        low_stock_count=low_stock_count,

        recent_orders=recent_orders,
        low_stock_books=low_stock_books,

        status_labels=ORDER_STATUS_LABELS
    )


@app.route("/admin/orders")
def admin_orders():

    # 1. Nhận tham số từ URL
    keyword = request.args.get("q", "").strip()

    status = request.args.get("status", "")

    page = request.args.get(
        "page",
        1,
        type=int
    )

    # 2. Truy vấn số đơn theo từng trạng thái
    status_counts = db.session.execute(
        db.select(
            Order.status,
            func.count(Order.id)
        )
        .group_by(Order.status)
    ).all()

    # Chuyển kết quả thành dictionary
    counts = {
        ORDER_STATUS_PENDING: 0,
        ORDER_STATUS_SHIPPING: 0,
        ORDER_STATUS_COMPLETED: 0,
        ORDER_STATUS_CANCELLED: 0
    }

    for order_status, count in status_counts:
        counts[order_status] = count

    # Tổng số đơn
    total_orders = sum(counts.values())

    # 3. Truy vấn ban đầu
    query = db.select(Order)

    # 4. Lọc theo trạng thái
    if status in ORDER_STATUS_LABELS:

        query = query.where(
            Order.status == status
        )

    # 5. Tìm kiếm
    if keyword:

        conditions = [
            Order.customer_name.ilike(f"%{keyword}%"),
            Order.phone.ilike(f"%{keyword}%")
        ]

        # Nếu từ khóa là số, tìm theo mã đơn
        if keyword.isdigit():

            conditions.append(
                Order.id == int(keyword)
            )

        query = query.where(
            or_(*conditions)
        )

    # 6. Sắp xếp đơn mới nhất trước
    query = query.order_by(
        Order.created_at.desc()
    )

    # 7. Tính tổng số đơn và tổng giá trị
    summary_query = db.select(
        func.count(Order.id),
        func.coalesce(func.sum(Order.total), 0)
    )

    # Dùng cùng điều kiện lọc với truy vấn danh sách
    if status in ORDER_STATUS_LABELS:

        summary_query = summary_query.where(
            Order.status == status
        )

    if keyword:

        conditions = [
            Order.customer_name.ilike(f"%{keyword}%"),
            Order.phone.ilike(f"%{keyword}%")
        ]

        if keyword.isdigit():
            conditions.append(
                Order.id == int(keyword)
            )

        summary_query = summary_query.where(
            or_(*conditions)
        )

    summary = db.session.execute(
        summary_query
    ).one()

    filtered_count = summary[0]
    filtered_total = summary[1]

    # 8. Phân trang
    pagination = db.paginate(
        query,
        page=page,
        per_page=10,
        error_out=False
    )

    return render_template(
        "admin/orders/index.html",

        orders=pagination.items,
        pagination=pagination,

        keyword=keyword,
        current_status=status,

        counts=counts,
        total_orders=total_orders,

        filtered_count=filtered_count,
        filtered_total=filtered_total,

        status_labels=ORDER_STATUS_LABELS
    )



@app.route(
    "/admin/orders/<int:order_id>",
    methods=["GET", "POST"]
)
def admin_order_detail(order_id):

    # 1. Tìm đơn hàng
    order = db.get_or_404(Order, order_id)

    # 2. Xác định trạng thái có thể chuyển đến
    allowed_statuses = ORDER_STATUS_TRANSITIONS.get(
        order.status,
        []
    )

    # 3. Khởi tạo form
    form = OrderStatusForm()

    # Chỉ hiển thị các trạng thái hợp lệ
    form.status.choices = [
        (status, ORDER_STATUS_LABELS[status])
        for status in allowed_statuses
    ]

    # 4. Xử lý khi quản trị viên gửi form
    if form.validate_on_submit():

        new_status = form.status.data

        # Kiểm tra trạng thái mới có hợp lệ không
        if new_status not in ORDER_STATUS_TRANSITIONS.get(
            order.status, []
        ):

            flash(
                "Không thể chuyển sang trạng thái này!",
                "danger"
            )

            return redirect(
                url_for(
                    "admin_order_detail",
                    order_id=order.id
                )
            )

        try:

            # Nếu hủy đơn thì hoàn lại tồn kho
            if new_status == ORDER_STATUS_CANCELLED:

                for item in order.items:

                    book = db.session.get(
                        Book,
                        item.book_id
                    )

                    if book is not None:

                        book.stock += item.quantity

            # Cập nhật trạng thái đơn hàng
            order.status = new_status

            # Ghi nhận lịch sử trạng thái
            history = OrderStatusHistory(
                order_id=order.id,
                status=new_status,
                created_at=datetime.now()
            )

            db.session.add(history)

            # Lưu tất cả thay đổi
            db.session.commit()

            flash(
                "Cập nhật trạng thái đơn hàng thành công!",
                "success"
            )

        except Exception:

            db.session.rollback()

            flash(
                "Có lỗi xảy ra khi cập nhật đơn hàng!",
                "danger"
            )

        # PRG: Post -> Redirect -> Get
        return redirect(
            url_for(
                "admin_order_detail",
                order_id=order.id
            )
        )

    # 5. Lấy lịch sử thay đổi trạng thái
    histories = db.session.scalars(
        db.select(OrderStatusHistory)
        .where(
            OrderStatusHistory.order_id == order.id
        )
        .order_by(
            OrderStatusHistory.created_at.asc()
        )
    ).all()

    # 6. Tính lại tạm tính từ các dòng đơn hàng
    subtotal = sum(
        item.quantity * item.unit_price
        for item in order.items
    )

    return render_template(
        "admin/orders/detail.html",

        order=order,
        form=form,

        histories=histories,

        subtotal=subtotal,

        status_labels=ORDER_STATUS_LABELS
    )

@app.context_processor
def inject_admin_data():

    pending_count = db.session.scalar(
        db.select(func.count(Order.id))
        .where(Order.status == ORDER_STATUS_PENDING)
    )

    return {
        "pending_orders_count": pending_count
    }
    
    

@app.route("/books")
def store_books():

    # 1. Nhận từ khóa tìm kiếm
    keyword = request.args.get("q", "").strip()

    # 2. Nhận danh mục được chọn
    category_id = request.args.get(
        "category_id",
        type=int
    )

    # 3. Lấy danh sách danh mục
    categories = db.session.scalars(
        db.select(Category).order_by(Category.name)
    ).all()

    # 4. Tạo truy vấn sách
    query = db.select(Book)

    # 5. Tìm theo tên sách hoặc tác giả
    if keyword:

        query = query.where(
            or_(
                Book.title.ilike(f"%{keyword}%"),
                Book.author.ilike(f"%{keyword}%")
            )
        )

    # 6. Lọc theo danh mục
    if category_id is not None:

        query = query.where(
            Book.category_id == category_id
        )

    # 7. Sắp xếp sách mới nhất trước
    query = query.order_by(Book.id.desc())

    # 8. Thực thi truy vấn
    books = db.session.scalars(query).all()

    return render_template(
        "store/books/index.html",

        books=books,
        categories=categories,

        keyword=keyword,
        category_id=category_id
    )
    

@app.route("/books/<int:book_id>")
def store_book_detail(book_id):

    # Tìm sách theo ID
    book = db.get_or_404(Book, book_id)

    # Lấy số lượng sách đã có trong giỏ
    cart = session.get("cart", {})

    cart_quantity = int(
        cart.get(str(book.id), 0)
    )

    # Số lượng còn có thể thêm vào giỏ
    available_quantity = max(
        book.stock - cart_quantity,
        0
    )

    return render_template(
        "store/books/detail.html",

        book=book,

        cart_quantity=cart_quantity,
        available_quantity=available_quantity
    )
    
@app.context_processor
def inject_store_data():

    # Lấy giỏ hàng từ Session
    cart = session.get("cart", {})

    # Tính tổng số lượng sách
    cart_count = sum(
        int(quantity)
        for quantity in cart.values()
    )

    return {
        "cart_count": cart_count
    }
    


@app.route("/cart")
def cart_index():

    # 1. Lấy giỏ hàng
    cart = session.get("cart", {})

    cart_items = []

    subtotal = 0

    # 2. Chuyển các ID từ Session thành số nguyên
    book_ids = [
        int(book_id)
        for book_id in cart.keys()
    ]

    # 3. Truy vấn tất cả sách trong giỏ
    books = db.session.scalars(
        db.select(Book).where(
            Book.id.in_(book_ids)
        )
    ).all() if book_ids else []

    # 4. Tạo dictionary để tìm sách theo ID
    book_map = {
        book.id: book
        for book in books
    }

    # 5. Duyệt từng sản phẩm trong Session
    for book_id, quantity in cart.items():

        book = book_map.get(int(book_id))

        # Bỏ qua sách không còn tồn tại
        if book is None:
            continue

        quantity = int(quantity)

        # Giá lấy trực tiếp từ database
        line_total = book.price * quantity

        subtotal += line_total

        cart_items.append({
            "book": book,
            "quantity": quantity,
            "line_total": line_total
        })

    return render_template(
        "store/cart/index.html",

        cart_items=cart_items,

        subtotal=subtotal
    )


@app.route(
    "/cart/add/<int:book_id>",
    methods=["POST"]
)
def cart_add(book_id):

    # 1. Tìm sách
    book = db.get_or_404(Book, book_id)

    # 2. Nhận số lượng từ form
    quantity = request.form.get(
        "quantity",
        default=1,
        type=int
    )

    # 3. Kiểm tra số lượng hợp lệ
    if quantity is None or quantity < 1:

        flash(
            "Số lượng phải lớn hơn 0!",
            "danger"
        )

        return redirect(
            url_for(
                "store_book_detail",
                book_id=book.id
            )
        )

    # 4. Lấy giỏ hàng
    cart = session.get("cart", {})

    # Chuyển ID thành chuỗi vì key trong Session là string
    book_key = str(book.id)

    # 5. Lấy số lượng sách đã có
    current_quantity = int(
        cart.get(book_key, 0)
    )

    # 6. Kiểm tra tồn kho còn có thể thêm
    available_quantity = (
        book.stock - current_quantity
    )

    if quantity > available_quantity:

        flash(
            f"Chỉ có thể thêm tối đa "
            f"{max(available_quantity, 0)} cuốn "
            f"{book.title} vào giỏ!",
            "danger"
        )

    else:

        # 7. Cộng dồn số lượng
        cart[book_key] = (
            current_quantity + quantity
        )

        # 8. Cập nhật Session
        session["cart"] = cart

        flash(
            f"Đã thêm {quantity} × {book.title} vào giỏ hàng!",
            "success"
        )

    # 9. Quay lại trang trước
    next_url = request.form.get(
        "next",
        url_for("store_books")
    )

    # Chỉ cho phép redirect đến đường dẫn nội bộ
    if not next_url.startswith("/") or next_url.startswith("//"):

        next_url = url_for("store_books")

    return redirect(next_url)

# =========================
# CART: UPDATE QUANTITY
# =========================

@app.route(
    "/cart/<int:book_id>/<action>",
    methods=["POST"]
)
def cart_update(book_id, action):

    # 1. Lấy giỏ hàng
    cart = session.get("cart", {})

    book_key = str(book_id)

    # 2. Kiểm tra sách có trong giỏ không
    if book_key not in cart:

        flash(
            "Sách không tồn tại trong giỏ hàng!",
            "danger"
        )

        return redirect(url_for("cart_index"))

    # 3. Kiểm tra hành động
    if action not in ["increase", "decrease", "remove"]:

        flash("Thao tác không hợp lệ!", "danger")

        return redirect(url_for("cart_index"))

    # 4. Lấy thông tin sách
    book = db.session.get(Book, book_id)

    if book is None:

        cart.pop(book_key)

        session["cart"] = cart

        flash("Sách không còn tồn tại!", "warning")

        return redirect(url_for("cart_index"))

    # 5. Lấy số lượng hiện tại
    quantity = int(cart[book_key])

    # 6. Tăng số lượng
    if action == "increase":

        if quantity < book.stock:

            cart[book_key] = quantity + 1

            flash("Đã tăng số lượng sách!", "success")

        else:

            flash(
                "Số lượng đã đạt giới hạn tồn kho!",
                "warning"
            )

    # 7. Giảm số lượng
    elif action == "decrease":

        quantity -= 1

        if quantity <= 0:

            cart.pop(book_key)

        else:

            cart[book_key] = quantity

    # 8. Xóa sách khỏi giỏ
    elif action == "remove":

        cart.pop(book_key)

        flash(
            f"Đã xóa {book.title} khỏi giỏ hàng!",
            "success"
        )

    # 9. Cập nhật Session
    session["cart"] = cart

    # 10. PRG
    return redirect(url_for("cart_index"))

# =========================
# CART: CLEAR
# =========================

@app.route(
    "/cart/clear",
    methods=["POST"]
)
def cart_clear():

    # Xóa giỏ hàng khỏi Session
    session.pop("cart", None)

    flash(
        "Đã xóa toàn bộ giỏ hàng!",
        "success"
    )

    return redirect(url_for("cart_index"))
###
# run
###
if __name__ == "__main__":
    app.run(debug=True, port=8000)
