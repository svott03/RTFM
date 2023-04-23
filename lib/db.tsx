import * as mongoDB from "mongodb";
import * as dotenv from "dotenv";
import { ObjectId } from "mongodb";

export const collections: { chunks?: mongoDB.Collection } = {}

/*
DB_CONN_STRING="mongodb+srv://svott:Mongo1234@cluster0.v1wrvyg.mongodb.net/?retryWrites=true&w=majority"
DB_NAME="LavaLabDB"
COLLECTION_NAME="Oscilloscope.pdf"
*/

export class Chunk {
  constructor(public header: string, public chunk: string, public id?: ObjectId) { }
};


export async function connectToDatabase(document: string) {
  const DB_CONN_STRING = 'mongodb+srv://svott:Mongo1234@cluster0.v1wrvyg.mongodb.net/?retryWrites=true&w=majority';
  const COLLECTION_NAME = document;
  const DB_NAME = 'LavaLabDB';
  // const DB_CONN_STRING = process.env.DB_CONN_STRING;
  // const COLLECTION_NAME = process.env.COLLECTION_NAME;
  // const DB_NAME = process.env.DB_NAME;
  // dotenv.config();

  const client: mongoDB.MongoClient = new mongoDB.MongoClient(DB_CONN_STRING!);

  await client.connect();

  const db: mongoDB.Db = client.db(DB_NAME);

  const myCollection: mongoDB.Collection = db.collection(COLLECTION_NAME!);

  collections.chunks = myCollection;
  const docs = (await collections.chunks.find({}).toArray());
  let chunks = [];
  let headers = [];
  console.log("Header size: " + headers.length);
  console.log("Chumks size: " + chunks.length);
  for (let i = 0; i < docs.length; ++i) {
    let header_with_tag = "<h1><strong>" + docs[i].header + "</strong></h1>";
    headers.push(header_with_tag);
    chunks.push("<p>" + docs[i].chunk + "</p>");
  }

  console.log(headers[0]);
  console.log(chunks[0]);
  console.log(`Successfully connected to database: ${db.databaseName} and collection: ${myCollection.collectionName}`);
  var text = "";
  let count = 0;
  for (let i = 0; i < chunks.length; ++i) {
    text += headers[i];
    text += chunks[i];
    if (text.length > 0) {
      text += '<br>'
    }
  }
  text = text.replaceAll('\n', '<br>')
  console.log("TEXT IS" + text);
  return '<div class="homepage">' + text + 'This is the homepage data</div>'
}
