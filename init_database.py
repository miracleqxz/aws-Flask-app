"""Initialize RDS PostgreSQL database with tables and sample data"""
import psycopg2
from config import Config


def create_tables():
    print("RDS Database Initialization")
    
    try:
        conn = psycopg2.connect(
            host=Config.POSTGRES_HOST,
            port=Config.POSTGRES_PORT,
            database=Config.POSTGRES_DB,
            user=Config.POSTGRES_USER,
            password=Config.POSTGRES_PASSWORD
        )
        
        cursor = conn.cursor()
        
        print("\nCreating 'movies' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                year INTEGER NOT NULL,
                rating DECIMAL(3, 1) NOT NULL,
                genre VARCHAR(255) NOT NULL,
                director VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                poster_filename VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Movies table ready!")
        
        print("\nCreating 'search_queries' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id SERIAL PRIMARY KEY,
                query VARCHAR(255) NOT NULL,
                results_count INTEGER NOT NULL,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Search queries table ready!")
        
        # Check if movies exist
        cursor.execute("SELECT COUNT(*) FROM movies;")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("\nInserting sample movies...")
            
            movies = [
                ("The Shawshank Redemption", 1994, 9.3, "Drama", "Frank Darabont", 
                 "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.", "shawshank.jpg"),
                ("The Godfather", 1972, 9.2, "Crime, Drama", "Francis Ford Coppola",
                 "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.", "godfather.jpg"),
                ("The Dark Knight", 2008, 9.0, "Action, Crime, Drama", "Christopher Nolan",
                 "When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests.", "dark_knight.jpg"),
                ("The Matrix", 1999, 8.7, "Action, Sci-Fi", "Lana Wachowski, Lilly Wachowski",
                 "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.", "matrix.jpg"),
                ("Inception", 2010, 8.8, "Action, Sci-Fi, Thriller", "Christopher Nolan",
                 "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea.", "inception.jpg"),
                ("Interstellar", 2014, 8.6, "Adventure, Drama, Sci-Fi", "Christopher Nolan",
                 "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.", "interstellar.jpg"),
                ("Pulp Fiction", 1994, 8.8, "Crime, Drama", "Quentin Tarantino",
                 "The lives of two mob hitmen, a boxer, a gangster and his wife intertwine in four tales of violence and redemption.", "pulp_fiction.jpg"),
                ("Fight Club", 1999, 8.8, "Drama", "David Fincher",
                 "An insomniac office worker and a devil-may-care soap maker form an underground fight club that evolves into much more.", "fight_club.jpg"),
                ("Forrest Gump", 1994, 8.8, "Drama, Romance", "Robert Zemeckis",
                 "The presidencies of Kennedy and Johnson, the Vietnam War, and other historical events unfold from the perspective of an Alabama man.", "forrest_gump.jpg"),
                ("Parasite", 2019, 8.6, "Comedy, Drama, Thriller", "Bong Joon Ho",
                 "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.", "parasite.jpg"),
            ]
            
            cursor.executemany("""
                INSERT INTO movies (title, year, rating, genre, director, description, poster_filename)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, movies)
            
            print(f"Inserted {len(movies)} movies")
        else:
            print(f"Movies table already has {count} records")
        
        conn.commit()
        
        print("\n" + "=" * 50)
        print("Database initialization complete!")
        print("=" * 50)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == '__main__':
    create_tables()
