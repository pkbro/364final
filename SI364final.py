import os
from flask import Flask, render_template, session, redirect, request, url_for, flash

from flask_script import Manager, Shell

from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField, FileField, PasswordField, BooleanField, SelectMultipleField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
import requests

basedir = os.path.abspath(os.path.dirname(__file__))


app = Flask(__name__)
app.static_folder = 'static'
app.config['SECRET_KEY'] = 'hardtoguessstring'
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URL') or "postgresql://localhost/SI364finalpkbro"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app)


search_recipes = db.Table('search_recipes', db.Column('recipe_id', db.Integer, db.ForeignKey('recipe_table.id')), db.Column('search_id',db.Integer, db.ForeignKey('search_words.id')))

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Search(db.Model):
    __tablename__ = "search_words"
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    recipes = db.relationship('Recipe', secondary=search_recipes, backref=db.backref('search_words', lazy='dynamic'), lazy='dynamic')


class Recipe(db.Model):
    __tablename__ = "recipe_table"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250))
    publisher = db.Column(db.String(250))
    publisher_url = db.Column(db.String(250))
    rating = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    search_id = db.Column(db.Integer, db.ForeignKey("search_words.id"))
    image_id = db.Column(db.Integer, db.ForeignKey("imgs.id"))

class Image(db.Model):
    __tablename__ = "imgs"
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(250))



class RegisterForm(FlaskForm):
    email=StringField('Enter Email: ', validators=[Required(), Email(), Length(1,64)])
    username=StringField('Enter Username: ', validators=[Required(), Length(1,64), Regexp('^[A-Za-z][A-Za-z0-9]*$', 0, 'Usernames can only include numbers and letters')])
    password=PasswordField('Enter Password: ', validators=[Required(), EqualTo('password2', message="Passwords need to match")])
    password2=PasswordField('Confirm Password: ', validators=[Required()])
    submit=SubmitField('Register')


    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('This email has been registered already.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username taken')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')

def words_validate(form, field):
    if len(field.data.split()) < 1:
        raise ValidationError("Blank input not allowed")

def word_length_validate(form,field):
    if len(field.data) < 2:
        raise ValidationError("Please enter a proper ingredient or recipe")

class RecipeForm(FlaskForm):
    word_search = StringField("Search for a Recipe: ", validators=[Required(), words_validate, word_length_validate])
    submit = SubmitField('Search')


class UpdateButtonForm(FlaskForm):
    submit = SubmitField("Update")

class UpdateRating(FlaskForm):
    rating = FloatField('Enter your own rating of this recipe: ', validators=[Required()])
    submit = SubmitField("Update")


class DeleteButtonForm(FlaskForm):
    delete = SubmitField("Delete")

def get_or_create_img(db_session, img_url):
    pic = Image.query.filter_by(image_url=img_url).first()
    if pic:
        return pic
    else:
        pic1 = Image(image_url=img_url)


        db_session.add(pic1)
        db_session.commit()
        return pic1


def get_or_create_search(db_session, word_search, user_id):

    search = Search.query.filter_by(word=word_search).first()
    if search:
        return search
    else:
        print(word_search)
        search1 = Search(word=word_search, user_id=user_id)
        print(search1)

        db_session.add(search1)
        db_session.commit()
        return search1

def get_or_create_recipe(db_session, title, publisher, rating, user_id, word_search, publisher_url, img_url):
    recipe = Recipe.query.filter_by(title=title).first()
    if recipe:
        return recipe
    else:
        pic = get_or_create_img(db_session, img_url)
        search = get_or_create_search(db_session, word_search, user_id)
        recipe = Recipe(title=title, publisher=publisher, rating=rating, user_id=user_id, search_id=search.id, publisher_url=publisher_url,image_id= pic.id)
        db_session.add(recipe)
        db_session.commit()
        return recipe

def show_user():
    return current_user.id


#Allows users to login
@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(url_for('index'))
        flash('Password or username invalid. Try again please.')
    return render_template('login.html',form=form)

#Allows users to logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You were successfully logged out.')
    return redirect(url_for('index'))

#Allows for new users to register themselves
@app.route('/register',methods=["GET","POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Login abilities enabled.')
        return redirect(url_for('login'))
    return render_template('register.html',form=form)

#Navigation
@app.route('/', methods=['GET', 'POST'])
def index():
    recipes_ = Recipe.query.all()
    form = RecipeForm()
    if form.validate_on_submit():

        api_key = "802ce9977641a25d3c63957c99bd11d7"
        res = requests.get("http://food2fork.com/api/search", params={'key':api_key, 'q':form.word_search.data })
        res_data = json.loads(res.text)
        single_recipe = res_data['recipes'][0]
        get_or_create_recipe(db.session, single_recipe["title"], single_recipe["publisher"], single_recipe["social_rank"], current_user.id, form.word_search.data, single_recipe['publisher_url'], single_recipe['image_url'])
        return redirect(url_for('recipes_'))
    return render_template('index.html', form=form)


#List all recipes saved by a user
@app.route('/recipes_')
def recipes_():
    recs = Recipe.query.all()
    recipes_lst = []
    current_user_id = show_user()
    form = DeleteButtonForm()
    for r in recs:
        if r.user_id == current_user.id:
            i = Image.query.filter_by(id=r.image_id).first()
            recipes_lst.append((r.title, r.publisher, r.publisher_url, r.rating, i.image_url, r.id))
    return render_template('recipes.html', recipes = recipes_lst, form=form, c=current_user_id)

#List all searches by a user
@app.route('/search_list')
def search_list():
    searches_ = Search.query.all()
    s_words = []
    for s in searches_:
        if s.user_id == current_user.id:
            s_words.append(s.word)
    return render_template('searches.html', searches = s_words)

@app.route('/pre_update', methods=['GET','POST'])
def pre_update():
    recs = Recipe.query.all()
    recipes_lst = []
    form = UpdateButtonForm()
    for r in recs:
        if r.user_id == current_user.id:
            recipes_lst.append((r.title, r.publisher, r.publisher_url, r.rating, r.id))
    return render_template('pre_update.html', recipes = recipes_lst, form=form)


#Give option to update rating any saved recipe of the user
@app.route('/update/<recipe>', methods= ['GET', 'POST'])
def update(recipe):
    rec = Recipe.query.filter_by(id=recipe).first()
    form = UpdateRating()
    if form.validate_on_submit():
        rec.rating = form.rating.data
        db.session.commit()
        flash("Updated rating for: " + rec.title)
        return redirect(url_for('recipes_'))

    return render_template('update_rating.html', form=form, rec=rec)

@app.route('/delete/<recipe>',methods=["GET","POST"])
def delete(recipe):
    rec = Recipe.query.filter_by(id=recipe).first()
    db.session.delete(rec)
    db.session.commit()
    flash("Deleted " + rec.title + " Successfully")
    return redirect(url_for('recipes_'))

#List all publishers of recipes from recipes that have been searched
@app.route('/publishers')
def publishers():
    recipes_ = Recipe.query.all()
    pub = []
    for r in recipes_:
        if r.user_id == current_user.id:
            pub.append((r.publisher,r.publisher_url))
    return render_template('publishers.html', publishers = pub)



#Error handling for 404 errors
@app.errorhandler(404)
def pagenotfound(e):
    return render_template('404.html'), 404

#Error handling for 500 errors
@app.errorhandler(500)
def pagenotfound(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    db.create_all()
    manager.run()
