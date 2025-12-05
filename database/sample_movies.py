

SAMPLE_MOVIES = [
    {
        'title': 'The Shawshank Redemption',
        'year': 1994,
        'rating': 9.3,
        'genre': 'Drama',
        'director': 'Frank Darabont',
        'description': 'Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.',
        'poster_filename': 'shawshank.jpg'
    },
    {
        'title': 'The Godfather',
        'year': 1972,
        'rating': 9.2,
        'genre': 'Crime, Drama',
        'director': 'Francis Ford Coppola',
        'description': 'The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.',
        'poster_filename': 'godfather.jpg'
    },
    {
        'title': 'The Dark Knight',
        'year': 2008,
        'rating': 9.0,
        'genre': 'Action, Crime, Drama',
        'director': 'Christopher Nolan',
        'description': 'When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests.',
        'poster_filename': 'dark_knight.jpg'
    },
    {
        'title': 'Pulp Fiction',
        'year': 1994,
        'rating': 8.9,
        'genre': 'Crime, Drama',
        'director': 'Quentin Tarantino',
        'description': 'The lives of two mob hitmen, a boxer, a gangster and his wife intertwine in four tales of violence and redemption.',
        'poster_filename': 'pulp_fiction.jpg'
    },
    {
        'title': 'Forrest Gump',
        'year': 1994,
        'rating': 8.8,
        'genre': 'Drama, Romance',
        'director': 'Robert Zemeckis',
        'description': 'The presidencies of Kennedy and Johnson, the Vietnam War, and other historical events unfold from the perspective of an Alabama man.',
        'poster_filename': 'forrest_gump.jpg'
    },
    {
        'title': 'Inception',
        'year': 2010,
        'rating': 8.8,
        'genre': 'Action, Sci-Fi, Thriller',
        'director': 'Christopher Nolan',
        'description': 'A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea.',
        'poster_filename': 'inception.jpg'
    },
    {
        'title': 'The Matrix',
        'year': 1999,
        'rating': 8.7,
        'genre': 'Action, Sci-Fi',
        'director': 'Lana Wachowski, Lilly Wachowski',
        'description': 'A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.',
        'poster_filename': 'matrix.jpg'
    },
    {
        'title': 'Goodfellas',
        'year': 1990,
        'rating': 8.7,
        'genre': 'Biography, Crime, Drama',
        'director': 'Martin Scorsese',
        'description': 'The story of Henry Hill and his life in the mob, covering his relationship with his wife and his partners in crime.',
        'poster_filename': 'goodfellas.jpg'
    },
    {
        'title': 'Interstellar',
        'year': 2014,
        'rating': 8.6,
        'genre': 'Adventure, Drama, Sci-Fi',
        'director': 'Christopher Nolan',
        'description': 'A team of explorers travel through a wormhole in space in an attempt to ensure humanity\'s survival.',
        'poster_filename': 'interstellar.jpg'
    },
    {
        'title': 'The Lord of the Rings: The Return of the King',
        'year': 2003,
        'rating': 9.0,
        'genre': 'Adventure, Drama, Fantasy',
        'director': 'Peter Jackson',
        'description': 'Gandalf and Aragorn lead the World of Men against Sauron\'s army to draw his gaze from Frodo and Sam.',
        'poster_filename': 'lotr_return.jpg'
    },
    {
        'title': 'Fight Club',
        'year': 1999,
        'rating': 8.8,
        'genre': 'Drama',
        'director': 'David Fincher',
        'description': 'An insomniac office worker and a devil-may-care soap maker form an underground fight club.',
        'poster_filename': 'fight_club.jpg'
    },
    {
        'title': 'Star Wars: Episode V',
        'year': 1980,
        'rating': 8.7,
        'genre': 'Action, Adventure, Fantasy',
        'director': 'Irvin Kershner',
        'description': 'After the Rebels are brutally overpowered by the Empire, Luke Skywalker begins Jedi training with Yoda.',
        'poster_filename': 'star_wars_5.jpg'
    },
    {
        'title': 'The Silence of the Lambs',
        'year': 1991,
        'rating': 8.6,
        'genre': 'Crime, Drama, Thriller',
        'director': 'Jonathan Demme',
        'description': 'A young FBI cadet must receive the help of an incarcerated cannibal killer to catch another serial killer.',
        'poster_filename': 'silence_lambs.jpg'
    },
    {
        'title': 'Saving Private Ryan',
        'year': 1998,
        'rating': 8.6,
        'genre': 'Drama, War',
        'director': 'Steven Spielberg',
        'description': 'Following the Normandy Landings, a group of U.S. soldiers go behind enemy lines to retrieve a paratrooper.',
        'poster_filename': 'saving_ryan.jpg'
    },
    {
        'title': 'Schindler\'s List',
        'year': 1993,
        'rating': 9.0,
        'genre': 'Biography, Drama, History',
        'director': 'Steven Spielberg',
        'description': 'In German-occupied Poland during World War II, industrialist Oskar Schindler becomes concerned for his Jewish workforce.',
        'poster_filename': 'schindlers.jpg'
    },
    {
        'title': 'The Green Mile',
        'year': 1999,
        'rating': 8.6,
        'genre': 'Crime, Drama, Fantasy',
        'director': 'Frank Darabont',
        'description': 'The lives of guards on Death Row are affected by one of their charges: a black man accused of child murder and rape.',
        'poster_filename': 'green_mile.jpg'
    },
    {
        'title': 'Parasite',
        'year': 2019,
        'rating': 8.5,
        'genre': 'Drama, Thriller',
        'director': 'Bong Joon Ho',
        'description': 'Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.',
        'poster_filename': 'parasite.jpg'
    },
    {
        'title': 'Gladiator',
        'year': 2000,
        'rating': 8.5,
        'genre': 'Action, Adventure, Drama',
        'director': 'Ridley Scott',
        'description': 'A former Roman General sets out to exact vengeance against the corrupt emperor who murdered his family.',
        'poster_filename': 'gladiator.jpg'
    },
    {
        'title': 'The Departed',
        'year': 2006,
        'rating': 8.5,
        'genre': 'Crime, Drama, Thriller',
        'director': 'Martin Scorsese',
        'description': 'An undercover cop and a mole in the police attempt to identify each other while infiltrating an Irish gang in Boston.',
        'poster_filename': 'departed.jpg'
    },
    {
        'title': 'Whiplash',
        'year': 2014,
        'rating': 8.5,
        'genre': 'Drama, Music',
        'director': 'Damien Chazelle',
        'description': 'A promising young drummer enrolls at a cut-throat music conservatory where his dreams of greatness are mentored by an instructor.',
        'poster_filename': 'whiplash.jpg'
    }
]
