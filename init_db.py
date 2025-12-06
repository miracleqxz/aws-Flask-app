import psycopg2
from config import Config


def create_tables():
    print("=" * 50)
    print("Database Initialization")
    print("=" * 50)
    
    try:
        conn = psycopg2.connect(
            host=Config.POSTGRES_HOST,
            port=Config.POSTGRES_PORT,
            database=Config.POSTGRES_DB,
            user=Config.POSTGRES_USER,
            password=Config.POSTGRES_PASSWORD,
            sslmode='require'  
        )
        
        cursor = conn.cursor()
        
        print("\nCreating 'movies' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                overview TEXT,                      
                poster_path VARCHAR(255),         
                release_date DATE,                 
                vote_average DECIMAL(3, 1),         
                popularity DECIMAL(10, 3),          
                original_language VARCHAR(10),      
                genre_ids INTEGER[],                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        
        cursor.execute("SELECT COUNT(*) FROM movies;")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("Inserting sample movies...")
            
            movies = [
                (1, "The Shawshank Redemption", 
                 "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.",
                 "shawshank.jpg", "1994-09-23", 9.3, 89.5, "en", [18]),
                
                (2, "The Godfather",
                 "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.",
                 "godfather.jpg", "1972-03-14", 9.2, 112.3, "en", [18, 80]),
                
                (3, "The Dark Knight",
                 "When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests.",
                 "dark_knight.jpg", "2008-07-18", 9.0, 98.7, "en", [28, 80, 18]),
                
                (4, "Schindler's List",
                 "In German-occupied Poland during World War II, industrialist Oskar Schindler gradually becomes concerned for his Jewish workforce after witnessing their persecution.",
                 "schindlers_list.jpg", "1993-02-04", 8.9, 85.2, "en", [18, 36, 10752]),
                
                (5, "The Lord of the Rings: The Return of the King",
                 "Gandalf and Aragorn lead the World of Men against Sauron's army to draw his gaze from Frodo and Sam as they approach Mount Doom with the One Ring.",
                 "lotr_return.jpg", "2003-12-17", 8.9, 96.8, "en", [12, 14, 28]),
                
                (6, "Pulp Fiction",
                 "The lives of two mob hitmen, a boxer, a gangster and his wife intertwine in four tales of violence and redemption.",
                 "pulp_fiction.jpg", "1994-09-10", 8.8, 87.2, "en", [80, 18]),
                
                (7, "Fight Club",
                 "An insomniac office worker and a devil-may-care soap maker form an underground fight club that evolves into much more.",
                 "fight_club.jpg", "1999-10-15", 8.8, 82.1, "en", [18]),
                
                (8, "Forrest Gump",
                 "The presidencies of Kennedy and Johnson, the Vietnam War, and other historical events unfold from the perspective of an Alabama man.",
                 "forrest_gump.jpg", "1994-07-06", 8.8, 91.8, "en", [35, 18, 10749]),
                
                (9, "Inception",
                 "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea.",
                 "inception.jpg", "2010-07-16", 8.8, 95.1, "en", [28, 878, 53]),
                
                (10, "Star Wars: Episode V",
                 "After the Rebels are brutally overpowered by the Empire on the ice planet Hoth, Luke Skywalker begins Jedi training.",
                 "star_wars_v.jpg", "1980-05-20", 8.7, 88.9, "en", [28, 12, 878]),
                
                (11, "The Matrix",
                 "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.",
                 "matrix.jpg", "1999-03-31", 8.7, 88.4, "en", [28, 878]),
                
                (12, "Goodfellas",
                 "The story of Henry Hill and his life in the mob, covering his relationship with his wife Karen Hill and his mob partners.",
                 "goodfellas.jpg", "1990-09-12", 8.7, 79.3, "en", [18, 80]),
                
                (13, "The Green Mile",
                 "The lives of guards on Death Row are affected by one of their charges: a black man accused of child murder and rape, yet who has a mysterious gift.",
                 "green_mile.jpg", "1999-12-10", 8.6, 83.5, "en", [80, 18, 14]),
                
                (14, "Interstellar",
                 "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
                 "interstellar.jpg", "2014-11-07", 8.6, 103.2, "en", [12, 18, 878]),
                
                (15, "The Silence of the Lambs",
                 "A young F.B.I. cadet must receive the help of an incarcerated and manipulative cannibal killer to help catch another serial killer.",
                 "silence_lambs.jpg", "1991-02-14", 8.6, 84.6, "en", [80, 18, 53]),
                
                (16, "Saving Private Ryan",
                 "Following the Normandy Landings, a group of U.S. soldiers go behind enemy lines to retrieve a paratrooper.",
                 "saving_ryan.jpg", "1998-07-24", 8.6, 91.4, "en", [18, 10752, 10749]),
                
                (17, "Parasite",
                 "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.",
                 "parasite.jpg", "2019-05-30", 8.6, 94.7, "ko", [35, 18, 53]),
                
                (18, "Gladiator",
                 "A former Roman General sets out to exact vengeance against the corrupt emperor who murdered his family and sent him into slavery.",
                 "gladiator.jpg", "2000-05-05", 8.5, 89.3, "en", [28, 18, 12]),
                
                (19, "The Departed",
                 "An undercover cop and a mole in the police attempt to identify each other while infiltrating an Irish gang in South Boston.",
                 "departed.jpg", "2006-10-06", 8.5, 86.1, "en", [18, 53, 80]),
                
                (20, "Whiplash",
                 "A promising young drummer enrolls at a cut-throat music conservatory where his dreams of greatness are mentored by an instructor who will stop at nothing.",
                 "whiplash.jpg", "2014-10-10", 8.5, 82.9, "en", [18, 10402]),
            ]
            
            cursor.executemany("""
                INSERT INTO movies (id, title, overview, poster_path, release_date, vote_average, popularity, original_language, genre_ids)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
            """, movies)
            
            print(f"Inserted {len(movies)} movies")
        else:
            print(f"Movies table already has {count} records")
        
        print("Movies table ready!")
        
        print("\nCreating 'search_queries' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id SERIAL PRIMARY KEY,
                query VARCHAR(255) NOT NULL,
                results_count INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Search queries table ready!")
        
        print("\nCreating 'search_analytics' table...")  
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_analytics (
                id SERIAL PRIMARY KEY,
                query VARCHAR(255) NOT NULL,
                results_count INTEGER,
                cached BOOLEAN DEFAULT FALSE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_data JSONB
            );
        """)
        print("Search analytics table ready!")
        
        conn.commit()
        
        print("\n" + "=" * 50)
        print("Database initialization complete!")
        print("=" * 50)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    create_tables()